/* Compile both service sources without evaluating them or opening audio. */
(
var directory = thisProcess.nowExecutingPath.dirname;
var files = ["sequencer.scd", "bootstrap.scd", "tests/coordinator_service.scd"];
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
