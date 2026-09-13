/* Native, manifest-driven VSCO buffer admission and region playback. */
(
var directory = thisProcess.nowExecutingPath.dirname;
var manifestPath = directory +/+ "vsco-manifest.json";
var manifest = manifestPath.parseJSONFile;
var jsonAt = { |object, key| object[key.asString] ? object[key.asSymbol] };
var files = jsonAt.value(manifest, "files");
var programs = jsonAt.value(manifest, "programs");
var regions = jsonAt.value(manifest, "regions");

~omniSampleRoot = "OMNICHORD_SC_VSCO_ROOT".getenv ? "";
~omniSampleBudgetBytes = (
    ("OMNICHORD_SC_SAMPLE_RAM_MIB".getenv ? "4096").asInteger * 1024 * 1024
);
~omniSampleFiles = Dictionary.new;
~omniSamplePrograms = Dictionary.new;
~omniSampleRegions = Dictionary.new;
~omniSampleStates = Dictionary.new;
~omniSampleBuffers = Dictionary.new;
~omniSampleBufferBytes = 0;
~omniSampleRoundRobin = Dictionary.new;

files.do { |record|
    ~omniSampleFiles[jsonAt.value(record, "id").asString] = record;
};
programs.do { |record|
    var programId = jsonAt.value(record, "id").asString;
    ~omniSamplePrograms[programId] = record;
    ~omniSampleRegions[programId] = List.new;
};
regions.do { |record|
    var programId = jsonAt.value(record, "program_id").asString;
    ~omniSampleRegions[programId].add(record);
};

~omniSampleProgramName = { |program|
    var text = program.asString;
    if(text.beginsWith("sample.vsco.") and: {
        ~omniSamplePrograms[text].notNil
    }) { text } { nil }
};

~omniSampleStatusReply = { |program, revision, status, detail|
    if(~omniReplyAddress.notNil) {
        ~omniReply.value(
            ~omniReplyAddress,
            '/omni/v1/program/status',
            ~omniClientSession,
            program,
            revision,
            status,
            detail
        );
    };
};

~omniPrepareSampleProgram = { |program, revision|
    var programId = ~omniSampleProgramName.value(program);
    if(programId.notNil) {
        var stateKey = programId ++ "@" ++ revision.asInteger;
        var state = ~omniSampleStates[stateKey];
        if(state.isNil or: { state[\status] == \error }) {
            var sampleIds = ~omniSampleRegions[programId]
                .collect { |region| jsonAt.value(region, "sample_id").asString }
                .asSet.asArray;
            var newBytes = sampleIds.sum { |sampleId|
                if(~omniSampleBuffers[sampleId].isNil) {
                    jsonAt.value(~omniSampleFiles[sampleId], "decoded_bytes").asInteger
                } { 0 }
            };
            if((~omniSampleBufferBytes + newBytes) > ~omniSampleBudgetBytes) {
                ~omniSampleStates[stateKey] = (
                    status: \error,
                    detail: "program-combination-exceeds-memory-profile"
                );
                ~omniSampleStatusReply.value(
                    programId,
                    revision,
                    "error",
                    "program-combination-exceeds-memory-profile"
                );
            } {
                ~omniSampleStates[stateKey] = (status: \loading, detail: "loading");
                Routine({
                    sampleIds.do { |sampleId|
                        if(~omniSampleBuffers[sampleId].isNil) {
                            var file = ~omniSampleFiles[sampleId];
                            var relative = jsonAt.value(file, "relative_path").asString;
                            ~omniSampleBuffers[sampleId] = Buffer.read(
                                s,
                                ~omniSampleRoot +/+ relative
                            );
                            ~omniSampleBufferBytes = ~omniSampleBufferBytes
                                + jsonAt.value(file, "decoded_bytes").asInteger;
                        };
                    };
                    s.sync;
                    ~omniSampleStates[stateKey] = (status: \ready, detail: "ready");
                    ~omniSampleStatusReply.value(
                        programId, revision, "ready", "ready"
                    );
                    nil
                }).play(AppClock);
            };
        } {
            ~omniSampleStatusReply.value(
                programId,
                revision,
                state[\status].asString,
                state[\detail].asString
            );
        };
    };
};

~omniSampleReady = { |program, revision|
    var state = ~omniSampleStates[
        program.asString ++ "@" ++ revision.asInteger
    ];
    state.notNil and: { state[\status] == \ready }
};

~omniSelectSampleRegions = { |program, logicalKey, velocity|
    var programRecord = ~omniSamplePrograms[program.asString];
    var articulation = jsonAt.value(programRecord, "default_articulation").asString;
    var midiVelocity = (velocity.clip(0, 1) * 127).round.asInteger;
    var random = 1.0.rand;
    var selected = ~omniSampleRegions[program.asString].select { |region|
        (logicalKey >= jsonAt.value(region, "key_lo").asInteger)
        and: { logicalKey <= jsonAt.value(region, "key_hi").asInteger }
        and: { midiVelocity >= jsonAt.value(region, "velocity_lo").asInteger }
        and: { midiVelocity <= jsonAt.value(region, "velocity_hi").asInteger }
        and: { jsonAt.value(region, "articulation_id").asString == articulation }
        and: { random >= jsonAt.value(region, "random_lo").asFloat }
        and: { random <= jsonAt.value(region, "random_hi").asFloat }
    };
    var rrLength = selected.collect { |region|
        jsonAt.value(region, "rr_length") ? 0
    }.maxItem ? 0;
    if(rrLength > 0) {
        var counterKey = program.asString ++ "/" ++ logicalKey.asString;
        var position = ((~omniSampleRoundRobin[counterKey] ? 0) % rrLength) + 1;
        ~omniSampleRoundRobin[counterKey] = position;
        selected = selected.select { |region|
            var candidate = jsonAt.value(region, "rr_position");
            candidate.isNil or: { candidate.asInteger == position }
        };
    };
    selected
};

SynthDef(\omniSampleMono, {
    |out=0, buffer=0, rate=1, velocity=0.7, gain=1, gainDb=0,
     attack=0.001, release=0.2, gate=1, pan=0, pitchBendBus=0|
    var bend = In.kr(pitchBendBus, 1).max(0.01);
    var playback = PlayBuf.ar(
        1, buffer, BufRateScale.kr(buffer) * rate * bend,
        doneAction: Done.freeSelf
    );
    var envelope = EnvGen.kr(
        Env.asr(attack.max(0.001), 1, release.max(0.005)),
        gate,
        doneAction: Done.freeSelf
    );
    Out.ar(
        out,
        Pan2.ar(playback, pan)
            * envelope * velocity.clip(0, 1) * gain * gainDb.dbamp
    );
}).add;

SynthDef(\omniSampleStereo, {
    |out=0, buffer=0, rate=1, velocity=0.7, gain=1, gainDb=0,
     attack=0.001, release=0.2, gate=1, pan=0, pitchBendBus=0|
    var bend = In.kr(pitchBendBus, 1).max(0.01);
    var playback = PlayBuf.ar(
        2, buffer, BufRateScale.kr(buffer) * rate * bend,
        doneAction: Done.freeSelf
    );
    var envelope = EnvGen.kr(
        Env.asr(attack.max(0.001), 1, release.max(0.005)),
        gate,
        doneAction: Done.freeSelf
    );
    Out.ar(
        out,
        Balance2.ar(playback[0], playback[1], pan)
            * envelope * velocity.clip(0, 1) * gain * gainDb.dbamp
    );
}).add;

~omniSpawnSampleVoice = {
    |owner, handle, program, revision, logicalKey, velocity, logicalBus|
    var selected = ~omniSelectSampleRegions.value(program, logicalKey, velocity);
    if(selected.notEmpty) {
        var group = Group.tail(~omniSourceGroup);
        var remaining = selected.size;
        var record = (
            sourceNode: group,
            outputNode: nil,
            releaseMode: \gated,
            sample: true,
            acid: false,
            owner: owner.asString,
            logicalKey: logicalKey.asInteger,
            program: program.asString
        );
        ~omniVoices[handle] = record;
        selected.do { |region|
            var sampleId = jsonAt.value(region, "sample_id").asString;
            var file = ~omniSampleFiles[sampleId];
            var buffer = ~omniSampleBuffers[sampleId];
            var channels = jsonAt.value(file, "channels").asInteger;
            var center = jsonAt.value(region, "key_center").asFloat;
            var tune = jsonAt.value(region, "tune_cents").asFloat;
            var envelope = jsonAt.value(region, "envelope");
            var node = Synth.tail(
                group,
                if(channels == 1) { \omniSampleMono } { \omniSampleStereo },
                [
                    \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
                    \buffer, buffer.bufnum,
                    \rate, 2 ** ((logicalKey - center + (tune / 100)) / 12),
                    \velocity, velocity,
                    \gainDb, jsonAt.value(region, "gain_db").asFloat,
                    \attack, jsonAt.value(envelope, "attack_sec").asFloat,
                    \release, jsonAt.value(envelope, "release_sec").asFloat,
                    \pitchBendBus, ~omniBendBus.index
                ]
            );
            node.onFree {
                remaining = remaining - 1;
                if(remaining <= 0) {
                    group.free;
                    if(~omniVoices[handle] === record) {
                        ~omniVoices.removeAt(handle);
                    };
                };
            };
        };
        true
    } {
        false
    }
};

("LB_OMNICHORD_VSCO_INDEX_LOADED programs=" ++ programs.size
    ++ " regions=" ++ regions.size).postln;
)
