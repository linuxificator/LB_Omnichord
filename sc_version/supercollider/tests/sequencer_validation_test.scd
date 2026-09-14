/* Receiver-side event payload and authored nesting validation smoke test. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;

~omniLanguagePort = 57149;
~omniClientSession = "validation-test";
~omniReplyAddress = nil;
~omniClock = TempoClock.new(2);
~omniTransportEpoch = 0;
~omniTransportRunning = false;
~omniReply = { };
~omniSessionValid = { false };
~omniReleaseHandle = { };
~omniSetHandle = { };
~omniPanic = { };
~omniSpawnVoice = { };
~omniSpawnDrum = { };

(directory +/+ "sequencer.scd").load;

if(~omniEventValidationError.value("launch", ["child"]).notNil) {
    Error("valid launch payload was rejected").throw;
};
if(~omniEventValidationError.value("launch", []).asString
    != "invalid-event-payload-size") {
    Error("invalid launch payload size was accepted").throw;
};
if(~omniEventValidationError.value(
    "gateBegin", ["snare", "fill", 0, "drumHit"]
).asString != "gate-duration-must-be-positive") {
    Error("nonpositive gate duration was accepted").throw;
};
if(~omniEventValidationError.value(
    "noteOn", ["voice", "owner", "program", 1, 60, 261.6, 0.8,
        "ordinary", 0, 0.0, 11]
).asString != "invalid-logical-bus") {
    Error("out-of-range note bus was accepted").throw;
};
if(~omniEventValidationError.value(
    "drumHit", ["rhythm/drums", "low_primary/kick", "program", 1,
        "kick", 36, 0.8, 0]
).notNil) {
    Error("valid drum payload was rejected").throw;
};

"LB_OMNICHORD_SC_SEQUENCER_VALIDATION_OK".postln;
0.exit;
)
