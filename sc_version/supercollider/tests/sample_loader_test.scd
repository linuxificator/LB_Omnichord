/* Evaluate the VSCO data index and region selector without opening audio. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var failed = false;
var selection;

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
if(~omniSampleProgramName.value("sample.vsco.fluteexpvib").isNil) {
    failed = true;
    "VSCO_PROGRAM_LOOKUP_FAILED".postln;
};
selection = ~omniSelectSampleRegions.value(
    "sample.vsco.fluteexpvib", 60, 0.5
);
if(selection.isEmpty) {
    failed = true;
    "VSCO_REGION_SELECTION_FAILED".postln;
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
if(~omniEvictSampleBytes.value(0).not) {
    failed = true;
    "VSCO_ZERO_PRESSURE_EVICTION_FAILED".postln;
};
if(failed) { 1.exit } {
    "VSCO_SAMPLE_LOADER_TEST_OK".postln;
    0.exit
};
)
