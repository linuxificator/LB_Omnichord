/*
 * LB Omnichord headless SuperCollider engine bootstrap.
 *
 * This file is deliberately self-contained for the first Linux vertical
 * slice.  It is started by the source/package supervisor, never imported by
 * the Qt process.  Control is accepted only on the configured loopback port.
 */
(
var languagePort = ("OMNICHORD_SC_PORT".getenv ? "57140").asInteger;
var sampleRate = ("OMNICHORD_SC_SAMPLE_RATE".getenv ? "48000").asInteger;
var blockSize = ("OMNICHORD_SC_BLOCK_SIZE".getenv ? "64").asInteger;
var maxNodes = ("OMNICHORD_SC_MAX_NODES".getenv ? "4096").asInteger;
var memKiB = ("OMNICHORD_SC_MEM_KIB".getenv ? "262144").asInteger;
var protocolVersion = 1;
var validateOnly = ("OMNICHORD_SC_VALIDATE_ONLY".getenv ? "0").asInteger == 1;
var scriptDirectory = thisProcess.nowExecutingPath.dirname;

~omniReady = false;
~omniLanguagePort = languagePort;
~omniClientSession = nil;
~omniEngineSession = ("sc-" ++ UniqueID.next.asString);
~omniVoices = IdentityDictionary.new;
~omniGestures = IdentityDictionary.new;
~omniMessageIds = IdentitySet.new;
~omniPrograms = IdentityDictionary.new;
~omniBusLevels = Array.fill(11, 1.0);
~omniRoomLevels = [0.0, 0.0];
~omniClock = TempoClock.new(108 / 60);
~omniTransportEpoch = 0;
~omniTransportRunning = false;
~omniReplyAddress = nil;

thisProcess.openUDPPort(languagePort);

~omniReply = { |address, path ... args|
    NetAddr(address.ip, address.port).sendMsg(path, *args);
};

~omniSessionValid = { |message|
    (~omniClientSession.notNil) and: { message[1].asString == ~omniClientSession };
};

~omniProgramKey = { |program, revision|
    program.asString ++ "@" ++ revision.asInteger.asString
};

~omniProgramArgs = { |program, revision|
    var record = ~omniPrograms[~omniProgramKey.value(program, revision)];
    var args = List.new;
    if(record.notNil) {
        record[\values].keysValuesDo { |name, value|
            if(["gain", "attack", "release", "brightness"].includes(name)) {
                args.add(name.asSymbol);
                args.add(value);
            };
        };
    };
    args.asArray
};

~omniReleaseHandle = { |handle|
    var record = ~omniVoices.removeAt(handle.asString);
    if(record.notNil) {
        record[\node].set(\gate, 0);
    };
};

~omniReleaseOwner = { |owner|
    var handles = List.new;
    ~omniVoices.keysValuesDo { |handle, record|
        if(record[\owner] == owner.asString) { handles.add(handle) };
    };
    handles.do(~omniReleaseHandle);
};

~omniPanic = {
    var handles = ~omniVoices.keys.asArray;
    handles.do(~omniReleaseHandle);
    ~omniGestures.clear;
};

OSCdef(\omniHello, { |message, time, address|
    var requested = message[2].asInteger;
    var replyPort = message[3].asInteger;
    ~omniClientSession = message[1].asString;
    if(replyPort > 0) { address = NetAddr(address.ip, replyPort) };
    ~omniReplyAddress = address;
    if(requested != protocolVersion) {
        ~omniReply.value(
            address,
            '/omni/v1/ready',
            ~omniEngineSession,
            protocolVersion,
            "builtin.vertical-slice.v1",
            "protocol-mismatch"
        );
    } {
        ~omniReply.value(
            address,
            '/omni/v1/ready',
            ~omniEngineSession,
            protocolVersion,
            "builtin.vertical-slice.v1",
            if(~omniReady) { "ready" } { "booting" }
        );
    };
}, '/omni/v1/hello', recvPort: languagePort);

OSCdef(\omniShutdown, { |message|
    if(~omniSessionValid.value(message)) {
        ~omniPanic.value;
        s.quit;
        SystemClock.sched(0.2, { 0.exit; nil });
    };
}, '/omni/v1/shutdown', recvPort: languagePort);

OSCdef(\omniProgramPrepare, { |message|
    if(~omniSessionValid.value(message)) {
        var owner = message[3].asString;
        var program = message[4].asString;
        var revision = message[5].asInteger;
        var logicalBus = message[6].asInteger.clip(0, 10);
        var key = ~omniProgramKey.value(program, revision);
        ~omniPrograms[key] = (
            owner: owner,
            program: program,
            revision: revision,
            logicalBus: logicalBus,
            values: IdentityDictionary.new
        );
    };
}, '/omni/v1/program/prepare', recvPort: languagePort);

OSCdef(\omniProgramValue, { |message|
    if(~omniSessionValid.value(message)) {
        var key = ~omniProgramKey.value(message[4], message[5]);
        var record = ~omniPrograms[key];
        if(record.notNil) {
            record[\values][message[6].asString] = message[7].asFloat;
        };
    };
}, '/omni/v1/program/value', recvPort: languagePort);

(scriptDirectory +/+ "sequencer.scd").load;

if(validateOnly) {
    "LB_OMNICHORD_SC_SYNTAX_OK".postln;
    0.exit;
};

s = Server.local;
s.options.sampleRate = sampleRate;
s.options.blockSize = blockSize;
s.options.maxNodes = maxNodes;
s.options.memSize = memKiB;
s.options.numInputBusChannels = 0;
s.options.numOutputBusChannels = 2;
s.options.bindAddress = "127.0.0.1";

s.waitForBoot({
    SynthDef(\omniVoice, {
        |out=0, freq=440, velocity=0.7, gate=1, gain=1, pan=0,
         bendBus=0, attack=0.008, release=0.22, brightness=0.55|
        var bend = In.kr(bendBus, 1).max(0.01);
        var pitched = freq.max(10) * bend;
        var env = EnvGen.kr(
            Env.adsr(attack.max(0.001), 0.12, 0.72, release.max(0.005)),
            gate,
            doneAction: Done.freeSelf
        );
        var cutoff = (pitched * (3 + (brightness.clip(0, 1) * 10)))
            .clip(80, SampleRate.ir * 0.45);
        var source = (VarSaw.ar(pitched, 0, 0.42, 0.42)
            + Pulse.ar(pitched * 0.5, 0.48, 0.20)
            + SinOsc.ar(pitched, 0, 0.12));
        var signal = RLPF.ar(source, cutoff, 0.55);
        Out.ar(out, Pan2.ar(signal * env * velocity.clip(0, 1) * gain, pan));
    }).add;

    SynthDef(\omniDrum, { |out=0, note=36, velocity=0.7, gain=1|
        var isKick = note < 41;
        var isHat = note > 49;
        var bodyFreq = note.midicps.clip(45, 420);
        var body = SinOsc.ar(
            XLine.kr(bodyFreq * 2.2, bodyFreq, 0.06),
            0,
            EnvGen.kr(Env.perc(0.001, 0.28), doneAction: 0)
        );
        var noise = HPF.ar(WhiteNoise.ar, if(isHat) { 5000 } { 900 })
            * EnvGen.kr(
                Env.perc(0.001, if(isHat) { 0.09 } { 0.20 }),
                doneAction: 0
            );
        var envelope = EnvGen.kr(
            Env.perc(0.001, if(isKick) { 0.34 } { 0.24 }),
            doneAction: Done.freeSelf
        );
        var signal = Select.ar(isHat, [body + (noise * 0.35), noise]);
        Out.ar(out, (signal * envelope * velocity.clip(0, 1) * gain) ! 2);
    }).add;

    SynthDef(\omniBusStrip, {
        |in=0, out=0, roomOut=0, gain=1, roomSend=1|
        var signal = In.ar(in, 2);
        Out.ar(out, signal * gain);
        Out.ar(roomOut, signal * roomSend);
    }).add;

    SynthDef(\omniRoom, {
        |in=0, out=0, level=0, room=0.5, damping=0.5, master=1|
        var signal = In.ar(in, 2);
        var wet = FreeVerb2.ar(
            signal[0], signal[1], 1,
            room.clip(0, 1), damping.clip(0, 1)
        );
        Out.ar(out, wet * level.max(0) * master.clip(0, 1));
    }).add;

    s.sync;

    ~omniSourceGroup = Group.head(s);
    ~omniMixGroup = Group.after(~omniSourceGroup);
    ~omniFxGroup = Group.after(~omniMixGroup);
    ~omniBendBus = Bus.control(s, 1);
    ~omniBendBus.set(1.0);
    ~omniLogicalBuses = Array.fill(11, { Bus.audio(s, 2) });
    ~omniRoomBuses = Array.fill(2, { Bus.audio(s, 2) });
    ~omniBusStrips = Array.fill(11, { |logical|
        var roomIndex = if(logical <= 3) { 0 } { 1 };
        Synth.tail(~omniMixGroup, \omniBusStrip, [
            \in, ~omniLogicalBuses[logical].index,
            \out, 0,
            \roomOut, ~omniRoomBuses[roomIndex].index,
            \gain, 1,
            \roomSend, if((logical == 0) or: { logical == 10 }) { 0 } { 1 }
        ])
    });
    ~omniRooms = Array.fill(2, { |roomIndex|
        Synth.tail(~omniFxGroup, \omniRoom, [
            \in, ~omniRoomBuses[roomIndex].index,
            \out, 0,
            \level, 0
        ])
    });

    ~omniSpawnVoice = {
        |owner, handle, program, revision, logicalKey, frequency,
         velocity, logicalBus, extraArgs|
        ~omniReleaseHandle.value(handle);
        ~omniVoices[handle] = (
            node: Synth.tail(~omniSourceGroup, \omniVoice, [
                \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
                \freq, frequency,
                \velocity, velocity,
                \bendBus, ~omniBendBus.index
            ] ++ ~omniProgramArgs.value(program, revision) ++ (extraArgs ? [])),
            owner: owner.asString,
            logicalKey: logicalKey.asInteger,
            program: program.asString
        );
    };

    ~omniSpawnDrum = { |note, velocity, logicalBus|
        Synth.tail(~omniSourceGroup, \omniDrum, [
            \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
            \note, note,
            \velocity, velocity
        ]);
    };

    ~omniReady = true;
    ("LB_OMNICHORD_SC_READY port=" ++ languagePort).postln;
}, {
    "LB_OMNICHORD_SC_BOOT_FAILED".postln;
    2.exit;
});

OSCdef(\omniNoteOn, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        var messageId = message[2].asInteger;
        var owner = message[3].asString;
        var handle = message[4].asString;
        var logicalKey = message[7].asInteger;
        var frequency = message[8].asFloat;
        var velocity = message[9].asFloat;
        var logicalBus = message[10].asInteger.clip(0, 10);
        if(~omniMessageIds.includes(messageId).not) {
            ~omniMessageIds.add(messageId);
            ~omniSpawnVoice.value(
                owner, handle, message[5], message[6], logicalKey,
                frequency, velocity, logicalBus, []
            );
        };
    };
}, '/omni/v1/note/on', recvPort: languagePort);

OSCdef(\omniNoteOff, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        ~omniReleaseHandle.value(message[4].asString);
    };
}, '/omni/v1/note/off', recvPort: languagePort);

OSCdef(\omniVoiceSet, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        var record = ~omniVoices[message[3].asString];
        var parameter = message[4].asString;
        var value = message[5].asFloat;
        if(record.notNil) {
            if(parameter == "frequency_hz") { record[\node].set(\freq, value) };
            if(parameter == "gain") { record[\node].set(\gain, value) };
            if(parameter == "brightness") { record[\node].set(\brightness, value) };
        };
    };
}, '/omni/v1/voice/set', recvPort: languagePort);

OSCdef(\omniOwnerRelease, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        ~omniReleaseOwner.value(message[3].asString);
    };
}, '/omni/v1/owner/release', recvPort: languagePort);

OSCdef(\omniGestureNote, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        var owner = message[3].asString;
        var handle = message[4].asString;
        var program = message[5].asString;
        var logicalKey = message[6].asInteger;
        var frequency = message[7].asFloat;
        var velocity = message[8].asFloat;
        var logicalBus = message[9].asInteger.clip(0, 10);
        var tailSeconds = message[10].asFloat.max(0.01);
        var voiceLimit = message[11].asInteger.max(1);
        var state = ~omniGestures[owner] ? (handles: List.new, token: 0);
        var duplicate = state[\handles].detect { |oldHandle|
            var old = ~omniVoices[oldHandle];
            old.notNil and: { old[\logicalKey] == logicalKey }
        };
        if(duplicate.notNil) {
            state[\handles].remove(duplicate);
            ~omniReleaseHandle.value(duplicate);
        };
        while { state[\handles].size >= voiceLimit } {
            ~omniReleaseHandle.value(state[\handles].removeAt(0));
        };
        ~omniSpawnVoice.value(
            owner, handle, program, 1, logicalKey, frequency,
            velocity, logicalBus, []
        );
        state[\handles].add(handle);
        state[\token] = state[\token] + 1;
        ~omniGestures[owner] = state;
        SystemClock.sched(tailSeconds, {
            var current = ~omniGestures[owner];
            if(current.notNil and: { current[\token] == state[\token] }) {
                current[\handles].do(~omniReleaseHandle);
                current[\handles].clear;
            };
            nil
        });
    };
}, '/omni/v1/gesture/note', recvPort: languagePort);

OSCdef(\omniDrumHit, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        var logicalBus = message[6].asInteger.clip(0, 10);
        ~omniSpawnDrum.value(
            message[4].asInteger,
            message[5].asFloat,
            logicalBus
        );
    };
}, '/omni/v1/drum/hit', recvPort: languagePort);

OSCdef(\omniBusLevel, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        var logicalBus = message[3].asInteger.clip(0, 10);
        var level = message[4].asFloat.max(0);
        ~omniBusLevels[logicalBus] = level;
        ~omniBusStrips[logicalBus].set(\gain, level);
    };
}, '/omni/v1/mixer/bus-level', recvPort: languagePort);

OSCdef(\omniRoomSet, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        var roomIndex = message[3].asInteger.clip(0, 1);
        ~omniRoomLevels[roomIndex] = message[4].asFloat.max(0);
        ~omniRooms[roomIndex].set(
            \level, ~omniRoomLevels[roomIndex],
            \room, message[5].asFloat.clip(0, 1),
            \damping, message[6].asFloat.clip(0, 1)
        );
    };
}, '/omni/v1/mixer/room', recvPort: languagePort);

OSCdef(\omniRoomSend, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        var logicalBus = message[3].asInteger.clip(0, 10);
        ~omniBusStrips[logicalBus].set(\roomSend, message[4].asFloat.max(0));
    };
}, '/omni/v1/mixer/room-send', recvPort: languagePort);

OSCdef(\omniBend, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        ~omniBendBus.set(2 ** message[3].asFloat);
    };
}, '/omni/v1/global/pitch-bend', recvPort: languagePort);

OSCdef(\omniPanicMessage, { |message|
    if(~omniReady and: { ~omniSessionValid.value(message) }) {
        ~omniPanic.value;
        ~omniBendBus.set(1.0);
    };
}, '/omni/v1/panic', recvPort: languagePort);
)
