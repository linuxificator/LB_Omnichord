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
~omniVoices = Dictionary.new;
~omniGestures = Dictionary.new;
~omniBusLevels = Array.fill(11, 1.0);
~omniRoomLevels = [0.0, 0.0];
~omniClock = TempoClock.new(108 / 60);
~omniTransportEpoch = 0;
~omniTransportRunning = false;
~omniReplyAddress = nil;
~omniDrumOrdinal = 0;
~omniDrumProgram = "sample.vsco.gm-styleperc";
~omniPitchBendOctaves = 0.0;

thisProcess.openUDPPort(languagePort);
(scriptDirectory +/+ "protocol_runtime.scd").load;
(scriptDirectory +/+ "program_registry.scd").load;

~omniReply = { |address, path ... args|
    NetAddr(address.ip, address.port).sendMsg(path, *args);
};

~omniSetPitchBend = { |octaves|
    var ratio;
    ~omniPitchBendOctaves = octaves.asFloat;
    ratio = 2 ** ~omniPitchBendOctaves;
    if(~omniBendBus.notNil) { ~omniBendBus.set(ratio) };
    ~omniVoices.values.do { |record|
        if(record[\nativeName].notNil and: {
            record[\baseFrequency].notNil
        }) {
            record[\sourceNode].set(
                \freq,
                record[\baseFrequency] * ratio
            );
        };
    };
};

~omniSessionValid = { |message|
    (~omniClientSession.notNil) and: { message[1].asString == ~omniClientSession };
};

~omniResetClientSession = {
    ~omniClock.clear;
    ~omniTransportRunning = false;
    ~omniPanic.value;
    ~omniMessageIds.clear;
    ~omniMessageIdOrder.clear;
    if(~omniTransactions.notNil) { ~omniTransactions.clear };
    if(~omniTransactionResults.notNil) { ~omniTransactionResults.clear };
    if(~omniTransactionResultOrder.notNil) { ~omniTransactionResultOrder.clear };
    if(~omniPendingActivations.notNil) { ~omniPendingActivations.clear };
    if(~omniInvalidateWake.notNil) { ~omniInvalidateWake.value };
    if(~omniResetSampleSession.notNil) { ~omniResetSampleSession.value };
    ~omniPrograms.clear;
    ~omniSetPitchBend.value(0.0);
};

~omniReleaseHandle = { |handle|
    var record = ~omniVoices.removeAt(handle.asString);
    if(record.notNil) {
        if(record[\sample] == true) {
            record[\sampleNodes].do { |sampleNode|
                sampleNode[\node].set(\gate, 0)
            };
        } {
        if(record[\outputNode].notNil) {
            record[\outputNode].set(\gate, 0);
            if(record[\releaseMode] == \gated) {
                record[\sourceNode].set(\gate, 0);
            };
        } {
            record[\sourceNode].set(\gate, 0);
        };
        };
    };
};

~omniSetHandle = { |handle, parameter, value|
    var record = ~omniVoices[handle.asString];
    var name = parameter.asString;
    if(record.notNil) {
        if(name == "frequency_hz") {
            record[\baseFrequency] = value;
            if(record[\acid] == true) {
                record[\sourceNode].set(
                    \slideEnabled, 1,
                    \freqTargetHz, value
                );
            } {
            if(record[\sample] == true) {
                ~omniRetuneSampleHandle.value(record, value);
            } {
                record[\sourceNode].set(
                    \freq,
                    value * (2 ** ~omniPitchBendOctaves)
                );
            };
            };
        };
        if(name == "accent") { record[\sourceNode].set(\t_accent, 1) };
        if(name == "gain") {
            (record[\outputNode] ? record[\sourceNode]).set(\gain, value)
        };
        if(name == "brightness") {
            record[\sourceNode].set(\brightness, value)
        };
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
    if(~omniExecutions.notNil) { ~omniExecutions.clear };
};

OSCdef(\omniHello, { |message, time, address|
    var requested = message[2].asInteger;
    var replyPort = message[3].asInteger;
    var incomingSession = message[1].asString;
    if(~omniClientSession.notNil and: {
        ~omniClientSession != incomingSession
    }) {
        ~omniResetClientSession.value;
    };
    ~omniClientSession = incomingSession;
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
    if(~omniSessionValid.value(message) and: {
        ~omniAcceptMessageId.value(message[2])
    }) {
        ~omniPanic.value;
        s.quit;
        SystemClock.sched(0.2, { 0.exit; nil });
    };
}, '/omni/v1/shutdown', recvPort: languagePort);

OSCdef(\omniProgramPrepare, { |message|
    if(~omniCommandValid.value(message)) {
        var owner = message[3].asString;
        var program = message[4].asString;
        var revision = message[5].asInteger;
        var logicalBus = message[6].asInteger.clip(0, 10);
        var key = ~omniProgramKey.value(owner, program, revision);
        if(~omniPrograms[key].isNil) {
            ~omniPrograms[key] = (
                owner: owner,
                program: program,
                revision: revision,
                logicalBus: logicalBus,
                values: Dictionary.new
            );
        };
        if(~omniPrepareSampleProgram.notNil) {
            ~omniPrepareSampleProgram.value(program, revision);
        };
    };
}, '/omni/v1/program/prepare', recvPort: languagePort);

OSCdef(\omniProgramValue, { |message|
    if(~omniCommandValid.value(message)) {
        var key = ~omniProgramKey.value(message[3], message[4], message[5]);
        var record = ~omniPrograms[key];
        if(record.notNil) {
            record[\values][message[6].asString] = message[7].asFloat;
        };
    };
}, '/omni/v1/program/value', recvPort: languagePort);

OSCdef(\omniProgramRelease, { |message|
    if(~omniCommandValid.value(message)) {
        var program = message[3].asString;
        var revision = message[4].asInteger;
        ~omniReleaseProgram.value(program, revision);
        if(~omniReleaseSampleProgram.notNil) {
            ~omniReleaseSampleProgram.value(program, revision);
        };
    };
}, '/omni/v1/program/release', recvPort: languagePort);

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
if("OMNICHORD_SC_SYNTH_PROGRAM".getenv.notNil) {
    s.options.program = "OMNICHORD_SC_SYNTH_PROGRAM".getenv;
};
if("OMNICHORD_SC_PLUGIN_PATH".getenv.notNil) {
    s.options.ugenPluginsPath = "OMNICHORD_SC_PLUGIN_PATH".getenv;
};

s.waitForBoot({
    (scriptDirectory +/+ "core_synthdefs.scd").load;

    (scriptDirectory +/+ "sclork_loader.scd").load;
    (scriptDirectory +/+ "acid_voices.scd").load;
    (scriptDirectory +/+ "sample_loader.scd").load;

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
        var nativeName = ~omniSclorkProgramName.value(program);
        var acidName = ~omniAcidProgramName.value(program);
        var sampleName = ~omniSampleProgramName.value(program);
        var preparedArgs = ~omniPreparedArgs.value(owner, program, revision)
            ++ (extraArgs ? []);
        var accentValue = 0;
        extraArgs.pairsDo { |name, value|
            if(name.asString == "accent") { accentValue = value };
        };
        ~omniReleaseHandle.value(handle);
        if(sampleName.notNil and: {
            ~omniSampleReady.value(sampleName, revision)
        }) {
            ~omniSpawnSampleVoice.value(
                owner, handle, sampleName, revision, logicalKey,
                frequency, velocity, logicalBus
            );
        } {
        if(acidName.notNil) {
            var sourceNode = Synth.tail(~omniSourceGroup, acidName, [
                    \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
                    \freqTargetHz, frequency,
                    \velocity, velocity,
                    \pitchBendBus, ~omniBendBus.index,
                    \t_accent, accentValue
                ] ++ ~omniAcidArgs.value(owner, program, revision));
            var record = (
                sourceNode: sourceNode,
                outputNode: nil,
                releaseMode: \gated,
                acid: true,
                owner: owner.asString,
                logicalKey: logicalKey.asInteger,
                program: program.asString
            );
            ~omniVoices[handle] = record;
            sourceNode.onFree {
                if(~omniVoices[handle] === record) {
                    ~omniVoices.removeAt(handle);
                };
            };
        } {
        if(nativeName.notNil and: {
            SynthDescLib.global.at(nativeName).notNil
        }) {
            var voiceBus = Bus.audio(s, 2);
            var outputRelease = 0.22;
            var sourceNode;
            var outputNode;
            var record;
            preparedArgs.pairsDo { |name, value|
                if(name.asString == "release") { outputRelease = value };
                if(name.asString == "release_ms") {
                    outputRelease = value / 1000;
                };
            };
            sourceNode = Synth.tail(
                ~omniSourceGroup,
                nativeName,
                ~omniSclorkArgs.value(
                    nativeName,
                    voiceBus.index,
                    frequency * (2 ** ~omniPitchBendOctaves),
                    preparedArgs
                )
            );
            outputNode = Synth.after(sourceNode, \omniVoiceOutput, [
                \in, voiceBus.index,
                \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
                \velocity, velocity,
                \release, outputRelease.max(0.005)
            ]);
            record = (
                sourceNode: sourceNode,
                outputNode: outputNode,
                voiceBus: voiceBus,
                nativeName: nativeName,
                baseFrequency: frequency,
                releaseMode: if(~omniSynthHasControl.value(nativeName, \gate)) {
                    \gated
                } {
                    \natural
                },
                acid: false,
                owner: owner.asString,
                logicalKey: logicalKey.asInteger,
                program: program.asString,
                cleaned: false
            );
            ~omniVoices[handle] = record;
            outputNode.onFree {
                if(record[\cleaned].not) {
                    record[\cleaned] = true;
                    sourceNode.free;
                    voiceBus.free;
                    if(~omniVoices[handle] === record) {
                        ~omniVoices.removeAt(handle);
                    };
                };
            };
            sourceNode.onFree {
                if(record[\cleaned].not) { outputNode.set(\gate, 0) };
            };
        } {
            var sourceNode = Synth.tail(~omniSourceGroup, \omniVoice, [
                \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
                \freq, frequency,
                \velocity, velocity,
                \bendBus, ~omniBendBus.index
                ] ++ ~omniGenericArgs.value(owner, program, revision));
            var record = (
                sourceNode: sourceNode,
                outputNode: nil,
                acid: false,
                owner: owner.asString,
                logicalKey: logicalKey.asInteger,
                program: program.asString
            );
            ~omniVoices[handle] = record;
            sourceNode.onFree {
                if(~omniVoices[handle] === record) {
                    ~omniVoices.removeAt(handle);
                };
            };
        };
        };
        };
    };

    ~omniSpawnDrum = { |role, requestedProgram, note, velocity, logicalBus|
        ~omniDrumOrdinal = ~omniDrumOrdinal + 1;
        if(~omniSampleReady.value(~omniDrumSampleProgram, 1)) {
            ~omniSpawnSampleVoice.value(
                "omni/drums",
                "drum/" ++ ~omniDrumOrdinal,
                ~omniDrumSampleProgram,
                1,
                ~omniMapDrumKey.value(role, note).clip(0, 127),
                note.asFloat.midicps,
                velocity,
                logicalBus
            );
        } {
            Synth.tail(~omniSourceGroup, \omniDrum, [
                \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
                \note, note,
                \velocity, velocity
            ]);
        };
    };

    ~omniPrepareSampleProgram.value(~omniDrumSampleProgram, 1);
    Routine({
        var stateKey = ~omniDrumSampleProgram ++ "@1";
        var state;
        while { ~omniReady.not } {
            state = ~omniSampleStates[stateKey];
            if(state.notNil and: { state[\status] == \ready }) {
                ~omniReady = true;
                ("LB_OMNICHORD_SC_READY port=" ++ languagePort).postln;
            };
            if(state.notNil and: { state[\status] == \error }) {
                ("LB_OMNICHORD_SC_BOOT_FAILED required-program="
                    ++ ~omniDrumSampleProgram ++ " detail="
                    ++ state[\detail]).postln;
                s.quit;
                2.exit;
            };
            if(~omniReady.not) { 0.02.wait };
        };
    }).play(AppClock);
}, {
    "LB_OMNICHORD_SC_BOOT_FAILED".postln;
    2.exit;
});

OSCdef(\omniNoteOn, { |message|
    if(~omniCommandValid.value(message)) {
        var owner = message[3].asString;
        var handle = message[4].asString;
        var logicalKey = message[7].asInteger;
        var frequency = message[8].asFloat;
        var velocity = message[9].asFloat;
        var logicalBus = message[10].asInteger.clip(0, 10);
        ~omniSpawnVoice.value(
            owner, handle, message[5], message[6], logicalKey,
            frequency, velocity, logicalBus, []
        );
    };
}, '/omni/v1/note/on', recvPort: languagePort);

OSCdef(\omniNoteOff, { |message|
    if(~omniCommandValid.value(message)) {
        ~omniReleaseHandle.value(message[4].asString);
    };
}, '/omni/v1/note/off', recvPort: languagePort);

OSCdef(\omniVoiceSet, { |message|
    if(~omniCommandValid.value(message)) {
        ~omniSetHandle.value(
            message[3].asString,
            message[4].asString,
            message[5].asFloat
        );
    };
}, '/omni/v1/voice/set', recvPort: languagePort);

OSCdef(\omniOwnerRelease, { |message|
    if(~omniCommandValid.value(message)) {
        ~omniReleaseOwner.value(message[3].asString);
    };
}, '/omni/v1/owner/release', recvPort: languagePort);

OSCdef(\omniGestureNote, { |message|
    if(~omniCommandValid.value(message)) {
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
    if(~omniCommandValid.value(message)) {
        var logicalBus = message[6].asInteger.clip(0, 10);
        ~omniSpawnDrum.value(
            "external_percussion",
            ~omniDrumProgram,
            message[4].asInteger,
            message[5].asFloat,
            logicalBus
        );
    };
}, '/omni/v1/drum/hit', recvPort: languagePort);

OSCdef(\omniBusLevel, { |message|
    if(~omniCommandValid.value(message)) {
        var logicalBus = message[3].asInteger.clip(0, 10);
        var level = message[4].asFloat.max(0);
        ~omniBusLevels[logicalBus] = level;
        ~omniBusStrips[logicalBus].set(\gain, level);
    };
}, '/omni/v1/mixer/bus-level', recvPort: languagePort);

OSCdef(\omniRoomSet, { |message|
    if(~omniCommandValid.value(message)) {
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
    if(~omniCommandValid.value(message)) {
        var logicalBus = message[3].asInteger.clip(0, 10);
        ~omniBusStrips[logicalBus].set(\roomSend, message[4].asFloat.max(0));
    };
}, '/omni/v1/mixer/room-send', recvPort: languagePort);

OSCdef(\omniBend, { |message|
    if(~omniCommandValid.value(message)) {
        ~omniSetPitchBend.value(message[3]);
    };
}, '/omni/v1/global/pitch-bend', recvPort: languagePort);

OSCdef(\omniPanicMessage, { |message|
    if(~omniCommandValid.value(message)) {
        ~omniPanic.value;
        ~omniSetPitchBend.value(0.0);
    };
}, '/omni/v1/panic', recvPort: languagePort);
)
