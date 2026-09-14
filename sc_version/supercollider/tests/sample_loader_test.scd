/* Evaluate the VSCO data index and region selector without opening audio. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var failed = false;
var selection;
var rrA1;
var rrA2;
var rrB1;
var triggerBase;
var attackRegion;
var releaseRegion;
var releaseKeyRegion;
var jsonAt = { |object, key| object[key.asString] ? object[key.asSymbol] };

(directory +/+ "sample_loader.scd").load;
if(~omniSampleBudgetBytes < 4294967296) {
    failed = true;
    ("VSCO_SAMPLE_BUDGET_OVERFLOW_FAILED "
        ++ ~omniSampleBudgetBytes).postln;
};
if(~omniSampleFiles.size != 3168) {
    failed = true;
    ("VSCO_FILE_COUNT_FAILED " ++ ~omniSampleFiles.size).postln;
};
if(~omniSamplePrograms.size != 75) {
    failed = true;
    ("VSCO_PROGRAM_COUNT_FAILED " ++ ~omniSamplePrograms.size).postln;
};
if(~omniSampleAliases.size != 105) {
    failed = true;
    ("VSCO_PLAYABLE_PROGRAM_COUNT_FAILED "
        ++ ~omniSampleAliases.size).postln;
};
if(~omniNativeDrumPads.size != 105) {
    failed = true;
    ("SC_NATIVE_DRUM_PAD_COUNT_FAILED "
        ++ ~omniNativeDrumPads.size).postln;
};
// Every explicit PCM pad must select the authored velocity layer at both
// inclusive boundaries.  Use a unique owner so round robin state is also
// proven to be independent per pad/layer rather than globally shared.
~omniDrumKits.keysValuesDo { |programId, kit|
    jsonAt.value(kit, "pads").keysValuesDo { |padId, pad|
        var sampleSet = ~omniDrumSampleSets[
            jsonAt.value(pad, "sample_set_id").asString
        ];
        jsonAt.value(sampleSet, "layers").do { |layer|
            var ids = jsonAt.value(layer, "round_robin_sample_ids")
                .collect { |value| value.asString }.asSet;
            [
                jsonAt.value(layer, "velocity_lo").asInteger,
                jsonAt.value(layer, "velocity_hi").asInteger
            ].do { |midiVelocity|
                var selected = ~omniSelectDrumSample.value(
                    "boundary/" ++ programId ++ "/" ++ padId,
                    programId,
                    padId,
                    midiVelocity / 127
                );
                if(selected.isNil or: {
                    ids.includes(selected[\sampleId].asString).not
                }) {
                    failed = true;
                    ("SC_PCM_DRUM_VELOCITY_BOUNDARY_FAILED program="
                        ++ programId ++ " pad=" ++ padId
                        ++ " velocity=" ++ midiVelocity).postln;
                };
            };
        };
    };
};
if(~omniSelectDrumSample.value(
    "missing", ~omniDrumKits.keys.asArray[0], "missing-pad", 0.5
).notNil) {
    failed = true;
    "SC_PCM_UNKNOWN_PAD_FAILED".postln;
};
if(
    (~omniNativeDrumPads["sc-808/timekeeper_primary"]["program_id"]
        ? ~omniNativeDrumPads["sc-808/timekeeper_primary"][\program_id])
        .asString != "sc.sclork.sosHats"
) {
    failed = true;
    "SC_NATIVE_DRUM_PROFILE_LOOKUP_FAILED".postln;
};
if(~omniSampleProgramName.value("sample.vsco.fluteexpvib").isNil) {
    failed = true;
    "VSCO_PROGRAM_LOOKUP_FAILED".postln;
};
if(~omniSampleProgramName.value(
    "sample.vsco.flute-ks.art.d-2-staccato"
).isNil) {
    failed = true;
    "VSCO_ARTICULATION_PROGRAM_LOOKUP_FAILED".postln;
};
selection = ~omniSelectSampleRegions.value(
    "sample.vsco.fluteexpvib", 60, 0.5
);
if(selection.isEmpty) {
    failed = true;
    "VSCO_REGION_SELECTION_FAILED".postln;
};
selection = ~omniSelectSampleRegions.value(
    "sample.vsco.fluteexpvib", 24, 0.5
);
if(selection.isEmpty or: {
    selection.any { |region|
        (region["key_lo"] ? region[\key_lo]).asInteger != 60
    }
}) {
    failed = true;
    "VSCO_BELOW_RANGE_NEAREST_REGION_FAILED".postln;
};
selection = ~omniSelectSampleRegions.value(
    "sample.vsco.fluteexpvib", 120, 0.5
);
if(selection.isEmpty or: {
    selection.any { |region|
        (region["key_hi"] ? region[\key_hi]).asInteger != 96
    }
}) {
    failed = true;
    "VSCO_ABOVE_RANGE_NEAREST_REGION_FAILED".postln;
};
selection = ~omniSelectSampleRegions.value(
    "sample.vsco.flute-ks.art.d-2-staccato", 72, 0.5
);
if(selection.isEmpty or: {
    selection.any { |region|
        (region["articulation_id"] ? region[\articulation_id]).asString
            != "d-2-staccato"
    }
}) {
    failed = true;
    "VSCO_EXPLICIT_ARTICULATION_SELECTION_FAILED".postln;
};
rrA1 = ~omniSelectSampleRegions.value(
    "sample.vsco.gm-styleperc", 36, 0.5, "part-a"
);
rrA2 = ~omniSelectSampleRegions.value(
    "sample.vsco.gm-styleperc", 36, 0.5, "part-a"
);
rrB1 = ~omniSelectSampleRegions.value(
    "sample.vsco.gm-styleperc", 36, 0.5, "part-b"
);
if(
    rrA1.size != 1 or: { rrA2.size != 1 } or: { rrB1.size != 1 }
    or: {
        (rrA1[0]["rr_position"] ? rrA1[0][\rr_position]).asInteger != 1
    }
    or: {
        (rrA2[0]["rr_position"] ? rrA2[0][\rr_position]).asInteger != 2
    }
    or: {
        (rrB1[0]["rr_position"] ? rrB1[0][\rr_position]).asInteger != 1
    }
) {
    failed = true;
    "VSCO_OWNER_SCOPED_ROUND_ROBIN_FAILED".postln;
};
if((~omniSamplePlaybackRate.value(440, 69, 0) - 1).abs > 0.000001) {
    failed = true;
    "VSCO_EQUAL_TEMPERAMENT_RATE_FAILED".postln;
};
if((~omniSamplePlaybackRate.value(442, 69, 0) - (442 / 440)).abs
    > 0.000001) {
    failed = true;
    "VSCO_FRACTIONAL_TUNING_RATE_FAILED".postln;
};
if((~omniSamplePlaybackRate.value(440, 69, 100) - (2 ** (1 / 12))).abs
    > 0.000001) {
    failed = true;
    "VSCO_SFZ_TUNE_RATE_FAILED".postln;
};
triggerBase = ~omniSampleRegions["sample.vsco.fluteexpvib"][0];
attackRegion = triggerBase.copy;
releaseRegion = triggerBase.copy;
releaseKeyRegion = triggerBase.copy;
attackRegion["trigger"] = "attack";
releaseRegion["trigger"] = "release";
releaseKeyRegion["trigger"] = "release_key";
releaseRegion["sample_id"] = "release-a";
releaseKeyRegion["sample_id"] = "release-b";
~omniSampleAliases["sample.trigger-test"] = (
    sourceProgramId: "sample.trigger-source",
    articulation: (
        triggerBase["articulation_id"] ? triggerBase[\articulation_id]
    ).asString
);
~omniSampleRegions["sample.trigger-source"] = List[
    attackRegion, releaseRegion, releaseKeyRegion
];
if(~omniSelectSampleRegions.value(
    "sample.trigger-test",
    (triggerBase["key_lo"] ? triggerBase[\key_lo]).asInteger,
    0.5,
    "trigger-test"
).size != 1) {
    failed = true;
    "VSCO_ATTACK_TRIGGER_FILTER_FAILED".postln;
};
if(~omniSampleReleaseCandidateIds.value(
    "sample.trigger-test",
    (triggerBase["key_lo"] ? triggerBase[\key_lo]).asInteger
).asSet != Set["release-a", "release-b"]) {
    failed = true;
    "VSCO_RELEASE_LIFETIME_CANDIDATES_FAILED".postln;
};
{
    var savedVoiceRefs = ~omniSampleVoiceRefs;
    var record = (
        lifetimeSampleIds: ["release-a", "release-b"],
        sampleLifetimePinned: true
    );
    ~omniSampleVoiceRefs = Dictionary.new;
    ~omniPinSampleIds.value(record[\lifetimeSampleIds]);
    ~omniReleaseSampleLifetime.value(record);
    ~omniReleaseSampleLifetime.value(record);
    if((~omniSampleVoiceRefs["release-a"] != 0) or: {
        ~omniSampleVoiceRefs["release-b"] != 0
    }) {
        failed = true;
        "VSCO_RELEASE_LIFETIME_UNPIN_IDEMPOTENCE_FAILED".postln;
    };
    ~omniSampleVoiceRefs = savedVoiceRefs;
}.value;
if(~omniSelectSampleRegions.value(
    "sample.trigger-test",
    (triggerBase["key_lo"] ? triggerBase[\key_lo]).asInteger,
    0.5,
    "trigger-test",
    "release"
).size != 1) {
    failed = true;
    "VSCO_RELEASE_TRIGGER_FILTER_FAILED".postln;
};
if(~omniEvictSampleBytes.value(0).not) {
    failed = true;
    "VSCO_ZERO_PRESSURE_EVICTION_FAILED".postln;
};
// Admission must not evict a buffer required by the program currently being
// prepared.  This is also the guard that makes shared-buffer preparation
// atomic before asynchronous scsynth reads complete.
{
    var savedBuffers = ~omniSampleBuffers;
    var savedBytes = ~omniSampleBufferBytes;
    var savedBudget = ~omniSampleBudgetBytes;
    var savedProgramRefs = ~omniSampleProgramRefs;
    var savedVoiceRefs = ~omniSampleVoiceRefs;
    ~omniSampleBuffers = Dictionary["protected" -> Object.new];
    ~omniSampleBufferBytes = 80;
    ~omniSampleBudgetBytes = 100;
    ~omniSampleProgramRefs = Dictionary.new;
    ~omniSampleVoiceRefs = Dictionary.new;
    if(~omniEvictSampleBytes.value(30, Set["protected"])) {
        failed = true;
        "VSCO_PROTECTED_ADMISSION_FAILED".postln;
    };
    if(~omniSampleBuffers["protected"].isNil) {
        failed = true;
        "VSCO_PROTECTED_BUFFER_EVICTED".postln;
    };
    ~omniSampleBuffers = savedBuffers;
    ~omniSampleBufferBytes = savedBytes;
    ~omniSampleBudgetBytes = savedBudget;
    ~omniSampleProgramRefs = savedProgramRefs;
    ~omniSampleVoiceRefs = savedVoiceRefs;
}.value;
if(failed) { 1.exit } {
    "VSCO_SAMPLE_LOADER_TEST_OK".postln;
    0.exit
};
)
