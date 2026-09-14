/* Immutable sequence executions retain their exact sample-program revision. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var key = "sample.vsco.flute-ks@7";
var counts = Dictionary.new;
var transaction;
var root;
var finite;

~omniLanguagePort = 57149;
~omniClientSession = "program-lifetime-test";
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
~omniRetainSequencePrograms = { |keys|
    keys.do { |item| counts[item] = (counts[item] ? 0) + 1 };
};
~omniReleaseSequencePrograms = { |keys|
    keys.do { |item| counts[item] = (counts[item] ? 0) - 1 };
};

(directory +/+ "sequencer.scd").load;

transaction = (
    lane: "sample-lifetime",
    generation: 1,
    alignment: 1,
    records: [
        (type: \definition, id: "sample-lifetime/root", revision: 1,
            kind: "root", period: 48, eventCount: 1),
        (type: \definition, id: "sample-lifetime/finite", revision: 1,
            kind: "finite", period: 0, eventCount: 2),
        (type: \event, definitionId: "sample-lifetime/root", tick: 0,
            ordinal: 0, action: "launch", atoms: ["sample-lifetime/finite"]),
        (type: \event, definitionId: "sample-lifetime/finite", tick: 0,
            ordinal: 0, action: "noteOn", atoms: [
                "voice", "rhythm/chords", "sample.vsco.flute-ks", 7,
                60, 261.625565, 0.7, "normal", 0, 0.0, 3
            ]),
        (type: \event, definitionId: "sample-lifetime/finite", tick: 24,
            ordinal: 1, action: "noteOff", atoms: ["voice", 0.0])
    ]
);
~omniPublishTransaction.value(transaction, 1);
root = ~omniDefinitions["sample-lifetime/root"];
finite = ~omniDefinitions["sample-lifetime/finite"];
if(root[\programKeys].asSet != Set[key]) {
    Error("root did not inherit its finite sample-program revision").throw;
};
if(finite[\programKeys].asSet != Set[key]) {
    Error("finite definition did not retain its sample-program revision").throw;
};

~omniTransportRunning = true;
~omniStartRoot.value(root, "sample-lifetime", 1, 0);
if(counts[key] != 1) {
    Error("root execution did not pin its sample-program revision").throw;
};
~omniStartFinite.value(finite[\id], "parent", 0);
if(counts[key] != 2) {
    Error("finite execution did not independently pin its revision").throw;
};
~omniRemoveRootExecutions.value("sample-lifetime", root[\id]);
if(counts[key] != 1) {
    Error("root replacement released a running finite child's pin").throw;
};
~omniExecutions.values.select { |item| item[\root].not }.do { |execution|
    ~omniAdvanceExecution.value(execution);
    ~omniAdvanceExecution.value(execution);
};
if(counts[key] != 0) {
    Error("completed finite execution leaked its sample-program pin").throw;
};

"LB_OMNICHORD_SC_SEQUENCE_PROGRAM_LIFETIME_OK".postln;
0.exit;
)
