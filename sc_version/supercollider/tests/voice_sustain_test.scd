/* Exercise production owner-scoped sustain policy without opening audio. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var released = List.new;
var failed = false;

~omniVoices = Dictionary[
    "a/60" -> (owner: "part/a"),
    "a/64" -> (owner: "part/a"),
    "b/60" -> (owner: "part/b")
];
~omniReleaseHandle = { |handle|
    var record = ~omniVoices.removeAt(handle.asString);
    ~omniSustainPending.removeAt(handle.asString);
    if(record.notNil) { released.add(handle.asString) };
};
(directory +/+ "voice_sustain.scd").load;

~omniSetOwnerSustain.value("part/a", true);
~omniRequestRelease.value("a/60");
~omniRequestRelease.value("b/60");
if(released.asArray != ["b/60"]) {
    failed = true;
    "SUSTAIN_OWNER_SCOPE_FAILED".postln;
};
if(~omniSustainPending["a/60"] != true) {
    failed = true;
    "SUSTAIN_DEFER_FAILED".postln;
};

~omniRequestRelease.value("missing");
if(released.asArray != ["b/60"]) {
    failed = true;
    "SUSTAIN_UNKNOWN_RELEASE_IDEMPOTENCE_FAILED".postln;
};

~omniSetOwnerSustain.value("part/a", false);
if(released.asArray != ["b/60", "a/60"]) {
    failed = true;
    "SUSTAIN_PEDAL_UP_RELEASE_FAILED".postln;
};
if(~omniVoices["a/64"].isNil) {
    failed = true;
    "SUSTAIN_UNRELEASED_NOTE_WAS_CUT_FAILED".postln;
};
if(~omniSustainPending.notEmpty) {
    failed = true;
    "SUSTAIN_PENDING_CLEANUP_FAILED".postln;
};

if(failed) { 1.exit } {
    "LB_OMNICHORD_SC_VOICE_SUSTAIN_OK".postln;
    0.exit;
};
)
