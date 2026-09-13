/* Compile both service sources without evaluating them or opening audio. */
(
var directory = thisProcess.nowExecutingPath.dirname;
var files = [
    "sequencer.scd",
    "bootstrap.scd",
    "sclork_loader.scd",
    "acid_voices.scd",
    "adapters/pulseRisset.scd",
    "adapters/pluck.scd",
    "adapters/sawSynth.scd",
    "adapters/waveguideFlute.scd",
    "tests/acid_voice_test.scd",
    "tests/coordinator_service.scd",
    "tests/sclork_loader_test.scd",
    "tests/sclork_compile_audit.scd"
];
var failed = false;
files.do { |name|
    var result = thisProcess.interpreter.compileFile(directory +/+ name);
    if(result.isNil) {
        failed = true;
        ("LB_OMNICHORD_SC_SYNTAX_FAILED " ++ name).postln;
    } {
        ("LB_OMNICHORD_SC_SYNTAX_OK " ++ name).postln;
    };
};
if(failed) { 1.exit } { 0.exit };
)
