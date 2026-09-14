/* Native, manifest-driven VSCO buffer admission and region playback. */
(
var directory = thisProcess.nowExecutingPath.dirname;
var manifestPath = directory +/+ "vsco-manifest.json";
var manifest = manifestPath.parseJSONFile;
var drumMap = (directory +/+ "drum-key-map.json").parseJSONFile;
var drumCatalogPath = "OMNICHORD_SC_DRUM_CATALOG".getenv;
var packagedDrumCatalog = directory.dirname
    +/+ "music/sc_expansion/sc_pcm_drumkits_v1.json";
var sourceDrumCatalog = directory.dirname
    +/+ "qt_frontend/music/sc_expansion/sc_pcm_drumkits_v1.json";
var packagedNativeDrumCatalog = directory.dirname
    +/+ "music/sc_expansion/sc_native_drumkits_v1.json";
var sourceNativeDrumCatalog = directory.dirname
    +/+ "qt_frontend/music/sc_expansion/sc_native_drumkits_v1.json";
var drumCatalog;
var nativeDrumCatalog;
var jsonAt = { |object, key| object[key.asString] ? object[key.asSymbol] };
var files = jsonAt.value(manifest, "files");
var programs = jsonAt.value(manifest, "programs");
var regions = jsonAt.value(manifest, "regions");

if(drumCatalogPath.isNil) {
    drumCatalogPath = if(PathName(packagedDrumCatalog).isFile) {
        packagedDrumCatalog
    } {
        sourceDrumCatalog
    };
};
drumCatalog = drumCatalogPath.parseJSONFile;
nativeDrumCatalog = if(PathName(packagedNativeDrumCatalog).isFile) {
    packagedNativeDrumCatalog.parseJSONFile
} {
    sourceNativeDrumCatalog.parseJSONFile
};

~omniSampleRoot = "OMNICHORD_SC_VSCO_ROOT".getenv ? "";
~omniSampleBudgetBytes = (
    ("OMNICHORD_SC_SAMPLE_RAM_MIB".getenv ? "4096").asFloat * 1024 * 1024
);
~omniSampleFiles = Dictionary.new;
~omniSamplePrograms = Dictionary.new;
~omniSampleRegions = Dictionary.new;
~omniSampleAliases = Dictionary.new;
~omniSampleStates = Dictionary.new;
~omniSampleBuffers = Dictionary.new;
~omniSampleBufferBytes = 0;
~omniSampleRoundRobin = Dictionary.new;
~omniSampleProgramRefs = Dictionary.new;
~omniSampleVoiceRefs = Dictionary.new;
~omniSampleLastUsed = Dictionary.new;
~omniSampleUseOrdinal = 0;
~omniDrumSampleProgram = jsonAt.value(
    jsonAt.value(drumCatalog, "kits")[0], "program_id"
).asString;
~omniDrumRoleKeys = Dictionary.new;
~omniDrumKits = Dictionary.new;
~omniDrumSampleSets = Dictionary.new;
~omniDrumChokes = Dictionary.new;
~omniNativeDrumPads = Dictionary.new;
~omniNativeDrumChokes = Dictionary.new;

jsonAt.value(drumMap, "role_keys").keysValuesDo { |role, key|
    ~omniDrumRoleKeys[role.asString] = key.asInteger;
};

~omniMapDrumKey = { |role, logicalKey|
    ~omniDrumRoleKeys[role.asString] ? logicalKey.asInteger
};

~omniTouchSample = { |sampleId|
    ~omniSampleUseOrdinal = ~omniSampleUseOrdinal + 1;
    ~omniSampleLastUsed[sampleId.asString] = ~omniSampleUseOrdinal;
};

~omniEvictSampleBytes = { |incomingBytes, protectedSampleIds|
    var needed = (
        ~omniSampleBufferBytes + incomingBytes - ~omniSampleBudgetBytes
    ).max(0);
    var candidates;
    if(needed <= 0) {
        true
    } {
        candidates = ~omniSampleBuffers.keys.select { |sampleId|
            ((~omniSampleProgramRefs[sampleId] ? 0) <= 0) and: {
                (~omniSampleVoiceRefs[sampleId] ? 0) <= 0
            } and: {
                protectedSampleIds.isNil or: {
                    protectedSampleIds.includes(sampleId).not
                }
            }
        }.asArray.sort { |left, right|
            (~omniSampleLastUsed[left] ? 0) < (~omniSampleLastUsed[right] ? 0)
        };
        candidates.do { |sampleId|
            if(needed > 0) {
                var bytes = jsonAt.value(
                    ~omniSampleFiles[sampleId], "decoded_bytes"
                ).asInteger;
                ~omniSampleBuffers.removeAt(sampleId).free;
                ~omniSampleBufferBytes = (~omniSampleBufferBytes - bytes).max(0);
                ~omniSampleLastUsed.removeAt(sampleId);
                needed = (needed - bytes).max(0);
            };
        };
        needed <= 0
    };
};

~omniReleaseSampleProgram = { |program, revision|
    var stateKey = program.asString ++ "@" ++ revision.asInteger;
    var state = ~omniSampleStates[stateKey];
    if(state.notNil) {
        if(state[\status] == \loading) {
            state[\cancelled] = true;
        } {
            if(state[\status] == \ready) {
                state[\sampleIds].do { |sampleId|
                    ~omniSampleProgramRefs[sampleId] = (
                        (~omniSampleProgramRefs[sampleId] ? 0) - 1
                    ).max(0);
                };
            };
            ~omniSampleStates.removeAt(stateKey);
            ~omniEvictSampleBytes.value(0);
        };
    };
};

~omniResetSampleSession = {
    var keep = ~omniDrumSampleProgram ++ "@1";
    ~omniSampleStates.keys.asArray.do { |stateKey|
        if(stateKey != keep) {
            var fields = stateKey.split($@);
            ~omniReleaseSampleProgram.value(
                fields[0], fields[1].asInteger
            );
        };
    };
    ~omniSampleRoundRobin.clear;
    ~omniDrumChokes.values.do { |node| node.set(\gate, 0) };
    ~omniDrumChokes.clear;
    ~omniNativeDrumChokes.values.do { |handle|
        ~omniReleaseHandle.value(handle)
    };
    ~omniNativeDrumChokes.clear;
};

files.do { |record|
    ~omniSampleFiles[jsonAt.value(record, "id").asString] = record;
};
jsonAt.value(drumCatalog, "sample_files").do { |record|
    ~omniSampleFiles[jsonAt.value(record, "id").asString] = record;
};
programs.do { |record|
    var programId = jsonAt.value(record, "id").asString;
    var defaultArticulation = jsonAt.value(
        record, "default_articulation"
    ).asString;
    ~omniSamplePrograms[programId] = record;
    ~omniSampleRegions[programId] = List.new;
    ~omniSampleAliases[programId] = (
        sourceProgramId: programId,
        articulation: defaultArticulation
    );
    jsonAt.value(record, "articulations").do { |articulation|
        var articulationId = articulation.asString;
        if(articulationId != defaultArticulation) {
            ~omniSampleAliases[
                programId ++ ".art." ++ articulationId
            ] = (
                sourceProgramId: programId,
                articulation: articulationId
            );
        };
    };
};
regions.do { |record|
    var programId = jsonAt.value(record, "program_id").asString;
    ~omniSampleRegions[programId].add(record);
};

jsonAt.value(drumCatalog, "sample_sets").do { |record|
    ~omniDrumSampleSets[
        jsonAt.value(record, "sample_set_id").asString
    ] = record;
};
jsonAt.value(drumCatalog, "kits").do { |record|
    var programId = jsonAt.value(record, "program_id").asString;
    var sampleIds = Set.new;
    ~omniDrumKits[programId] = record;
    jsonAt.value(record, "pads").keysValuesDo { |padId, pad|
        var sampleSet = ~omniDrumSampleSets[
            jsonAt.value(pad, "sample_set_id").asString
        ];
        jsonAt.value(sampleSet, "layers").do { |layer|
            jsonAt.value(layer, "round_robin_sample_ids").do { |sampleId|
                sampleIds.add(sampleId.asString);
            };
        };
    };
    ~omniSampleAliases[programId] = (
        sourceProgramId: programId,
        articulation: "drum-kit"
    );
    ~omniSampleRegions[programId] = sampleIds.asArray;
};

jsonAt.value(nativeDrumCatalog, "kits").do { |kit|
    var kitId = jsonAt.value(kit, "kit_id").asString;
    jsonAt.value(kit, "pads").keysValuesDo { |padId, pad|
        ~omniNativeDrumPads[kitId ++ "/" ++ padId.asString] = pad;
    };
};

~omniDrumKitSampleIds = { |programId|
    var value = ~omniSampleRegions[programId.asString];
    if(~omniDrumKits[programId.asString].notNil) { value } { nil }
};

~omniSampleProgramName = { |program|
    var text = program.asString;
    if(text.beginsWith("sample.vsco.") and: {
        ~omniSampleAliases[text].notNil
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
        var alias = ~omniSampleAliases[programId];
        var sourceProgramId = alias[\sourceProgramId];
        var articulation = alias[\articulation];
        var stateKey = programId ++ "@" ++ revision.asInteger;
        var state = ~omniSampleStates[stateKey];
        if(state.isNil or: { state[\status] == \error }) {
            var drumSampleIds = ~omniDrumKitSampleIds.value(sourceProgramId);
            var sampleIds = if(drumSampleIds.notNil) {
                drumSampleIds
            } {
                ~omniSampleRegions[sourceProgramId]
                    .select { |region|
                        jsonAt.value(region, "articulation_id").asString
                            == articulation
                    }
                    .collect { |region|
                        jsonAt.value(region, "sample_id").asString
                    }
                    .asSet.asArray
            };
            var newSampleIds = sampleIds.select { |sampleId|
                ~omniSampleBuffers[sampleId].isNil
            };
            var newBytes = newSampleIds.sum { |sampleId|
                if(~omniSampleBuffers[sampleId].isNil) {
                    jsonAt.value(~omniSampleFiles[sampleId], "decoded_bytes").asInteger
                } { 0 }
            };
            var missing = sampleIds.detect { |sampleId|
                var file = ~omniSampleFiles[sampleId];
                var relative = jsonAt.value(file, "relative_path").asString;
                PathName(~omniSampleRoot +/+ relative).isFile.not
            };
            if(missing.notNil) {
                ~omniSampleStates[stateKey] = (
                    status: \error,
                    detail: "sample-file-missing"
                );
                ~omniSampleStatusReply.value(
                    programId,
                    revision,
                    "error",
                    "sample-file-missing"
                );
            } {
            if(~omniEvictSampleBytes.value(newBytes, sampleIds.asSet).not) {
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
                state = (
                    status: \loading,
                    detail: "loading",
                    sampleIds: sampleIds,
                    cancelled: false
                );
                ~omniSampleStates[stateKey] = state;
                sampleIds.do { |sampleId|
                    ~omniSampleProgramRefs[sampleId] =
                        (~omniSampleProgramRefs[sampleId] ? 0) + 1;
                    ~omniTouchSample.value(sampleId);
                };
                // Buffer.read returns a buffer identity immediately and does
                // the file I/O asynchronously in scsynth.  Publish and account
                // those identities in this interpreter turn, before yielding
                // to AppClock.  A concurrent prepare can then share them and
                // cannot independently admit the same bytes or overrun the
                // configured budget.
                newSampleIds.do { |sampleId|
                    var file = ~omniSampleFiles[sampleId];
                    var relative = jsonAt.value(file, "relative_path").asString;
                    ~omniSampleBuffers[sampleId] = Buffer.read(
                        s,
                        ~omniSampleRoot +/+ relative,
                        startFrame: (jsonAt.value(file, "start_frame") ? 0).asInteger,
                        numFrames: -1
                    );
                    ~omniSampleBufferBytes = ~omniSampleBufferBytes
                        + jsonAt.value(file, "decoded_bytes").asInteger;
                };
                Routine({
                    s.sync;
                    if(state[\cancelled]) {
                        sampleIds.do { |sampleId|
                            ~omniSampleProgramRefs[sampleId] = (
                                (~omniSampleProgramRefs[sampleId] ? 0) - 1
                            ).max(0);
                        };
                        ~omniSampleStates.removeAt(stateKey);
                        ~omniEvictSampleBytes.value(0);
                    } {
                        state[\status] = \ready;
                        state[\detail] = "ready";
                        ~omniSampleStatusReply.value(
                            programId, revision, "ready", "ready"
                        );
                    };
                    nil
                }).play(AppClock);
            };
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

~omniSelectSampleRegions = {
    |program, logicalKey, velocity, owner="default", trigger="attack"|
    var alias = ~omniSampleAliases[program.asString];
    var sourceProgramId = alias[\sourceProgramId];
    var articulation = alias[\articulation];
    var midiVelocity = (velocity.clip(0, 1) * 127).round.asInteger;
    var random = 1.0.rand;
    var candidates = ~omniSampleRegions[sourceProgramId].select { |region|
        (midiVelocity >= jsonAt.value(region, "velocity_lo").asInteger)
        and: { midiVelocity <= jsonAt.value(region, "velocity_hi").asInteger }
        and: { jsonAt.value(region, "articulation_id").asString == articulation }
        and: { jsonAt.value(region, "trigger").asString == trigger.asString }
    };
    var nearestDistance = candidates.collect { |region|
        var low = jsonAt.value(region, "key_lo").asInteger;
        var high = jsonAt.value(region, "key_hi").asInteger;
        if(logicalKey < low) {
            low - logicalKey
        } {
            if(logicalKey > high) { logicalKey - high } { 0 }
        }
    }.minItem;
    var selected = candidates.select { |region|
        var low = jsonAt.value(region, "key_lo").asInteger;
        var high = jsonAt.value(region, "key_hi").asInteger;
        var distance = if(logicalKey < low) {
            low - logicalKey
        } {
            if(logicalKey > high) { logicalKey - high } { 0 }
        };
        (distance == nearestDistance)
        and: { random >= jsonAt.value(region, "random_lo").asFloat }
        and: { random < jsonAt.value(region, "random_hi").asFloat }
    };
    var rrLength = selected.collect { |region|
        var value = jsonAt.value(region, "rr_length");
        if(value.isNil) { 0 } { value.asInteger }
    }.maxItem ? 0;
    if(rrLength > 0) {
        var first = selected[0];
        var counterKey = owner.asString ++ "/" ++ program.asString
            ++ "/" ++ logicalKey.asString ++ "/" ++ articulation
            ++ "/" ++ jsonAt.value(first, "velocity_lo").asString
            ++ "-" ++ jsonAt.value(first, "velocity_hi").asString
            ++ "/" ++ rrLength.asString;
        var position = ((~omniSampleRoundRobin[counterKey] ? 0) % rrLength) + 1;
        ~omniSampleRoundRobin[counterKey] = position;
        selected = selected.select { |region|
            var candidate = jsonAt.value(region, "rr_position");
            candidate.isNil or: { candidate.asInteger == position }
        };
    };
    selected
};

// A held key may need a release recording after its program has been
// superseded.  Pin every release candidate for that key and articulation at
// attack time: release velocity and random/round-robin selection are not known
// until key-up, so pinning only one speculative region would be incorrect.
~omniSampleReleaseCandidateIds = { |program, logicalKey|
    var alias = ~omniSampleAliases[program.asString];
    if(alias.isNil) {
        []
    } {
        var candidates = ~omniSampleRegions[alias[\sourceProgramId]].select { |region|
            var trigger = jsonAt.value(region, "trigger").asString;
            (
                jsonAt.value(region, "articulation_id").asString
                    == alias[\articulation]
            )
            and: { (trigger == "release") or: { trigger == "release_key" } }
        };
        var nearestDistance = candidates.collect { |region|
            var low = jsonAt.value(region, "key_lo").asInteger;
            var high = jsonAt.value(region, "key_hi").asInteger;
            if(logicalKey < low) {
                low - logicalKey
            } {
                if(logicalKey > high) { logicalKey - high } { 0 }
            }
        }.minItem;
        candidates.select { |region|
            var low = jsonAt.value(region, "key_lo").asInteger;
            var high = jsonAt.value(region, "key_hi").asInteger;
            var distance = if(logicalKey < low) {
                low - logicalKey
            } {
                if(logicalKey > high) { logicalKey - high } { 0 }
            };
            distance == nearestDistance
        }.collect { |region|
            jsonAt.value(region, "sample_id").asString
        }.asSet.asArray
    }
};

~omniPinSampleIds = { |sampleIds|
    sampleIds.do { |sampleId|
        ~omniSampleVoiceRefs[sampleId] =
            (~omniSampleVoiceRefs[sampleId] ? 0) + 1;
        ~omniTouchSample.value(sampleId);
    };
};

~omniReleaseSampleLifetime = { |record|
    if(record[\sampleLifetimePinned] == true) {
        record[\lifetimeSampleIds].do { |sampleId|
            ~omniSampleVoiceRefs[sampleId] = (
                (~omniSampleVoiceRefs[sampleId] ? 0) - 1
            ).max(0);
        };
        record[\sampleLifetimePinned] = false;
    };
};

~omniSpawnSampleRelease = { |record, trigger, releaseVelocity|
    var selectionVelocity = if(releaseVelocity > 0) {
        releaseVelocity
    } {
        record[\velocity]
    };
    var selected = ~omniSelectSampleRegions.value(
        record[\program],
        record[\logicalKey],
        selectionVelocity,
        record[\owner] ++ "/" ++ trigger.asString,
        trigger
    );
    selected.do { |region|
        var sampleId = jsonAt.value(region, "sample_id").asString;
        var file = ~omniSampleFiles[sampleId];
        var buffer = ~omniSampleBuffers[sampleId];
        var channels = jsonAt.value(file, "channels").asInteger;
        var center = jsonAt.value(region, "key_center").asFloat;
        var tune = jsonAt.value(region, "tune_cents").asFloat;
        var envelope = jsonAt.value(region, "envelope");
        var node = Synth.tail(
            ~omniSourceGroup,
            if(channels == 1) { \omniSampleMono } { \omniSampleStereo },
            [
                \out, ~omniLogicalBuses[record[\logicalBus]].index,
                \buffer, buffer.bufnum,
                \rate, ~omniSamplePlaybackRate.value(
                    record[\frequencyHz], center, tune
                ),
                \velocity, record[\velocity]
                    * (0.5 + (selectionVelocity * 0.5)),
                \gainDb, jsonAt.value(region, "gain_db").asFloat,
                \attack, jsonAt.value(envelope, "attack_sec").asFloat,
                \release, jsonAt.value(envelope, "release_sec").asFloat,
                \pitchBendBus, ~omniBendBus.index
            ]
        );
        ~omniSampleVoiceRefs[sampleId] =
            (~omniSampleVoiceRefs[sampleId] ? 0) + 1;
        ~omniTouchSample.value(sampleId);
        node.onFree {
            ~omniSampleVoiceRefs[sampleId] = (
                (~omniSampleVoiceRefs[sampleId] ? 0) - 1
            ).max(0);
        };
    };
};

~omniPhysicalRelease = { |record, releaseVelocity|
    if(record[\sample] == true) {
        ~omniSpawnSampleRelease.value(record, "release_key", releaseVelocity);
    };
};

~omniFinalRelease = { |record, releaseVelocity|
    if(record[\sample] == true) {
        ~omniSpawnSampleRelease.value(record, "release", releaseVelocity);
    };
};

~omniSamplePlaybackRate = { |frequencyHz, keyCenter, tuneCents|
    (frequencyHz.asFloat / keyCenter.asFloat.midicps)
        * (2 ** (tuneCents.asFloat / 1200))
};

~omniSelectDrumSample = { |owner, program, padId, velocity|
    var kit = ~omniDrumKits[program.asString];
    var pads = jsonAt.value(kit, "pads");
    var pad = jsonAt.value(pads, padId.asString);
    var sampleSet = if(pad.notNil) {
        ~omniDrumSampleSets[jsonAt.value(pad, "sample_set_id").asString]
    } { nil };
    var midiVelocity = (velocity.clip(0, 1) * 127).round.asInteger.max(1);
    var layer = if(sampleSet.notNil) {
        jsonAt.value(sampleSet, "layers").detect { |candidate|
            (midiVelocity >= jsonAt.value(candidate, "velocity_lo").asInteger)
            and: {
                midiVelocity <= jsonAt.value(candidate, "velocity_hi").asInteger
            }
        }
    } { nil };
    if(layer.isNil) {
        nil
    } {
        var sampleIds = jsonAt.value(layer, "round_robin_sample_ids");
        var counterKey = owner.asString ++ "/" ++ program.asString ++ "/"
            ++ padId.asString ++ "/" ++ jsonAt.value(layer, "layer").asString;
        var position = (~omniSampleRoundRobin[counterKey] ? 0) % sampleIds.size;
        ~omniSampleRoundRobin[counterKey] = position + 1;
        (
            sampleId: sampleIds[position].asString,
            pad: pad,
            kit: kit
        )
    }
};

SynthDef(\omniDrumSampleMono, {
    |out=0, buffer=0, velocity=0.7, gainDb=0, playbackRate=1,
     maxDuration=1, fadeOut=0.02, highpass=0, lowpass=0,
     pan=0, gate=1|
    var fade = fadeOut.max(0.001).min(maxDuration.max(0.002) * 0.5);
    var duration = maxDuration.max(fade + 0.001);
    var playback = PlayBuf.ar(
        1, buffer, BufRateScale.kr(buffer) * playbackRate,
        doneAction: Done.freeSelf
    );
    var filtered = LPF.ar(
        HPF.ar(playback, highpass.max(20)),
        Select.kr(lowpass > 0, [20000, lowpass]).clip(20, 20000)
    );
    var lifetime = EnvGen.kr(
        Env([1, 1, 0], [duration - fade, fade]),
        doneAction: Done.freeSelf
    );
    var choke = EnvGen.kr(Env.asr(0.001, 1, fade), gate, doneAction: Done.freeSelf);
    Out.ar(out, Pan2.ar(filtered, pan) * lifetime * choke
        * velocity.clip(0, 1) * gainDb.dbamp);
}).add;

SynthDef(\omniDrumSampleStereo, {
    |out=0, buffer=0, velocity=0.7, gainDb=0, playbackRate=1,
     maxDuration=1, fadeOut=0.02, highpass=0, lowpass=0,
     pan=0, gate=1|
    var fade = fadeOut.max(0.001).min(maxDuration.max(0.002) * 0.5);
    var duration = maxDuration.max(fade + 0.001);
    var playback = PlayBuf.ar(
        2, buffer, BufRateScale.kr(buffer) * playbackRate,
        doneAction: Done.freeSelf
    );
    var filtered = LPF.ar(
        HPF.ar(playback, highpass.max(20)),
        Select.kr(lowpass > 0, [20000, lowpass]).clip(20, 20000)
    );
    var lifetime = EnvGen.kr(
        Env([1, 1, 0], [duration - fade, fade]),
        doneAction: Done.freeSelf
    );
    var choke = EnvGen.kr(Env.asr(0.001, 1, fade), gate, doneAction: Done.freeSelf);
    Out.ar(out, Balance2.ar(filtered[0], filtered[1], pan) * lifetime * choke
        * velocity.clip(0, 1) * gainDb.dbamp);
}).add;

~omniSpawnDrumSample = {
    |owner, handle, program, revision, padId, velocity, logicalBus|
    var selection;
    if(~omniSampleReady.value(program, revision).not) {
        false
    } {
        selection = ~omniSelectDrumSample.value(
            owner, program, padId, velocity
        );
        if(selection.isNil) {
            false
        } {
            var sampleId = selection[\sampleId];
            var pad = selection[\pad];
            var kit = selection[\kit];
            var file = ~omniSampleFiles[sampleId];
            var buffer = ~omniSampleBuffers[sampleId];
            var channels = jsonAt.value(file, "channels").asInteger;
            var chokeGroupValue = jsonAt.value(pad, "choke_group");
            var chokeKey = if(chokeGroupValue.isNil) { nil } {
                owner.asString ++ "/" ++ program.asString ++ "/"
                    ++ chokeGroupValue.asString
            };
            var node;
            if(chokeKey.notNil and: { ~omniDrumChokes[chokeKey].notNil }) {
                ~omniDrumChokes[chokeKey].set(\gate, 0);
            };
            node = Synth.tail(
                ~omniSourceGroup,
                if(channels == 1) {
                    \omniDrumSampleMono
                } {
                    \omniDrumSampleStereo
                },
                [
                    \out, ~omniLogicalBuses[logicalBus.clip(0, 10)].index,
                    \buffer, buffer.bufnum,
                    \velocity, velocity,
                    \gainDb, jsonAt.value(pad, "gain_db").asFloat
                        + jsonAt.value(kit, "kit_gain_db").asFloat,
                    \playbackRate, jsonAt.value(pad, "playback_rate").asFloat,
                    \maxDuration,
                        jsonAt.value(pad, "max_duration_ms").asFloat / 1000,
                    \fadeOut, jsonAt.value(pad, "fade_out_ms").asFloat / 1000,
                    \highpass, jsonAt.value(pad, "highpass_hz").asFloat,
                    \lowpass, jsonAt.value(pad, "lowpass_hz").asFloat,
                    \pan, jsonAt.value(pad, "pan").asFloat
                ]
            );
            ~omniSampleVoiceRefs[sampleId] =
                (~omniSampleVoiceRefs[sampleId] ? 0) + 1;
            ~omniTouchSample.value(sampleId);
            if(chokeKey.notNil) { ~omniDrumChokes[chokeKey] = node };
            node.onFree {
                ~omniSampleVoiceRefs[sampleId] = (
                    (~omniSampleVoiceRefs[sampleId] ? 0) - 1
                ).max(0);
                if(chokeKey.notNil and: { ~omniDrumChokes[chokeKey] === node }) {
                    ~omniDrumChokes.removeAt(chokeKey);
                };
            };
            true
        }
    }
};

SynthDef(\omniSampleMono, {
    |out=0, buffer=0, rate=1, velocity=0.7, gain=1, gainDb=0,
     attack=0.001, release=0.2, gate=1, gateControl=1, rateScale=1,
     pan=0, pitchBendBus=0|
    var bend = In.kr(pitchBendBus, 1).max(0.01);
    var playback = PlayBuf.ar(
        1, buffer, BufRateScale.kr(buffer) * rate * rateScale * bend,
        doneAction: Done.freeSelf
    );
    var envelope = EnvGen.kr(
        Env.asr(attack.max(0.001), 1, release.max(0.005)),
        gate * gateControl,
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
     attack=0.001, release=0.2, gate=1, gateControl=1, rateScale=1,
     pan=0, pitchBendBus=0|
    var bend = In.kr(pitchBendBus, 1).max(0.01);
    var playback = PlayBuf.ar(
        2, buffer, BufRateScale.kr(buffer) * rate * rateScale * bend,
        doneAction: Done.freeSelf
    );
    var envelope = EnvGen.kr(
        Env.asr(attack.max(0.001), 1, release.max(0.005)),
        gate * gateControl,
        doneAction: Done.freeSelf
    );
    Out.ar(
        out,
        Balance2.ar(playback[0], playback[1], pan)
            * envelope * velocity.clip(0, 1) * gain * gainDb.dbamp
    );
}).add;

~omniSpawnSampleVoice = {
    |owner, handle, program, revision, logicalKey, frequencyHz,
        velocity, logicalBus, oneShot=false|
    var selected = ~omniSelectSampleRegions.value(
        program, logicalKey, velocity, owner
    );
    if(selected.notEmpty) {
        var group = Group.tail(~omniSourceGroup);
        var gateBus = Bus.control(s, 1);
        var rateScaleBus = Bus.control(s, 1);
        var remaining = selected.size;
        var sampleNodes = List.new;
        var lifetimeSampleIds = if(oneShot) {
            []
        } {
            ~omniSampleReleaseCandidateIds.value(program, logicalKey)
        };
        var record = (
            sourceNode: group,
            outputNode: nil,
            releaseMode: \gated,
            sample: true,
            acid: false,
            owner: owner.asString,
            logicalKey: logicalKey.asInteger,
            program: program.asString,
            logicalBus: logicalBus.clip(0, 10),
            frequencyHz: frequencyHz.asFloat,
            initialFrequencyHz: frequencyHz.asFloat,
            velocity: velocity.asFloat.clip(0, 1),
            physicalReleased: false,
            finalized: false,
            oneShot: oneShot,
            lifetimeSampleIds: lifetimeSampleIds,
            sampleLifetimePinned: lifetimeSampleIds.notEmpty,
            sampleNodes: sampleNodes,
            gateBus: gateBus,
            gateBusAlive: true,
            rateScaleBus: rateScaleBus,
            rateScaleBusAlive: true
        );
        gateBus.set(1);
        rateScaleBus.set(1);
        ~omniPinSampleIds.value(lifetimeSampleIds);
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
                    \rate, ~omniSamplePlaybackRate.value(
                        frequencyHz, center, tune
                    ),
                    \velocity, velocity,
                    \gainDb, jsonAt.value(region, "gain_db").asFloat,
                    \attack, jsonAt.value(envelope, "attack_sec").asFloat,
                    \release, jsonAt.value(envelope, "release_sec").asFloat,
                    \pitchBendBus, ~omniBendBus.index
                ]
            );
            var sampleNode;
            ~omniSampleVoiceRefs[sampleId] =
                (~omniSampleVoiceRefs[sampleId] ? 0) + 1;
            ~omniTouchSample.value(sampleId);
            sampleNode = (
                node: node, sampleId: sampleId, center: center, tune: tune,
                alive: true
            );
            sampleNodes.add(sampleNode);
            node.map(\gateControl, gateBus, \rateScale, rateScaleBus);
            node.onFree {
                sampleNode[\alive] = false;
                ~omniSampleVoiceRefs[sampleId] = (
                    (~omniSampleVoiceRefs[sampleId] ? 0) - 1
                ).max(0);
                remaining = remaining - 1;
                if(remaining <= 0) {
                    group.free;
                    record[\gateBusAlive] = false;
                    record[\rateScaleBusAlive] = false;
                    gateBus.free;
                    rateScaleBus.free;
                    if((record[\oneShot] == true) or: {
                        record[\finalized] == true
                    }) {
                        ~omniReleaseSampleLifetime.value(record);
                    };
                    if(((record[\oneShot] == true) or: {
                        record[\finalized] == true
                    }) and: { ~omniVoices[handle] === record }) {
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

~omniRetuneSampleHandle = { |record, frequencyHz|
    record[\frequencyHz] = frequencyHz.asFloat;
    if(record[\rateScaleBusAlive]) {
        record[\rateScaleBus].set(
            frequencyHz.asFloat / record[\initialFrequencyHz].max(0.001)
        )
    };
};

~omniGateSampleHandle = { |record|
    if(record[\gateBusAlive]) {
        record[\gateBus].set(0)
    };
};

("LB_OMNICHORD_VSCO_INDEX_LOADED programs=" ++ programs.size
    ++ " regions=" ++ regions.size).postln;
)
