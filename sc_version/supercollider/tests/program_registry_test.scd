/* Verify that equal program identities never share mutable part parameters. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var failed = false;
var program = "sample.fixture";

(directory +/+ "program_registry.scd").load;
~omniPrograms[~omniProgramKey.value("part/a", program, 7)] = (
    owner: "part/a", program: program, revision: 7,
    values: Dictionary["gain" -> 0.25, "private" -> 1]
);
~omniPrograms[~omniProgramKey.value("part/b", program, 7)] = (
    owner: "part/b", program: program, revision: 7,
    values: Dictionary["gain" -> 0.75]
);
~omniPrograms[~omniProgramKey.value("part/a", program, 8)] = (
    owner: "part/a", program: program, revision: 8,
    values: Dictionary["gain" -> 0.9]
);

if(~omniPreparedArgs.value("part/a", program, 7).includesEqual(0.75)) {
    failed = true;
    "SC_PROGRAM_OWNER_PARAMETER_LEAK_FAILED".postln;
};
if(~omniPreparedArgs.value("part/b", program, 7).includesEqual(0.25)) {
    failed = true;
    "SC_PROGRAM_OWNER_PARAMETER_REVERSE_LEAK_FAILED".postln;
};
if(~omniGenericArgs.value("part/a", program, 7).includesEqual(\private)) {
    failed = true;
    "SC_PROGRAM_GENERIC_FILTER_FAILED".postln;
};
if(~omniReleaseProgram.value(program, 7) != 2) {
    failed = true;
    "SC_PROGRAM_RELEASE_COUNT_FAILED".postln;
};
if(~omniPrograms.size != 1 or: {
    ~omniPreparedArgs.value("part/a", program, 8).includesEqual(0.9).not
}) {
    failed = true;
    "SC_PROGRAM_RELEASE_REVISION_ISOLATION_FAILED".postln;
};

if(failed) { 1.exit } {
    "LB_OMNICHORD_SC_PROGRAM_REGISTRY_OK".postln;
    0.exit
};
)
