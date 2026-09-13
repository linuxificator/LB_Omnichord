/* Evaluate the VSCO data index and region selector without opening audio. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var failed = false;
var selection;

(directory +/+ "sample_loader.scd").load;
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
if(failed) { 1.exit } {
    "VSCO_SAMPLE_LOADER_TEST_OK".postln;
    0.exit
};
)
