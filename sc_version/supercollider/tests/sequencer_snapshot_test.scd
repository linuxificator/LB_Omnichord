/* Immutable-definition snapshot and atomic activation test; no audio server. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var event = { |tick| (
    type: \event,
    definitionId: "snapshot/child",
    tick: tick,
    ordinal: 0,
    action: "noteOff",
    atoms: ["voice", 0.0]
) };
var child = { |revision| (
    id: "snapshot/child",
    revision: revision,
    kind: "finite",
    lane: "snapshot",
    period: 0,
    eventCount: 1,
    events: [event.value(48)]
) };
var oldChild;
var newChild;
var activationDefinitions = Dictionary.new;
var revisions;
var queued;

~omniLanguagePort = 57149;
~omniClientSession = "snapshot-test";
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

oldChild = child.value(1);
newChild = child.value(2);
~omniDefinitions["snapshot/child"] = oldChild;
~omniLanes["snapshot"] = (generation: 1, definitionIds: []);
~omniStartFinite.value("snapshot/child", "parent-a", 0);

activationDefinitions["snapshot/child"] = newChild;
if(~omniDefinitions["snapshot/child"][\revision] != 1) {
    Error("staged definition became visible before activation").throw;
};
~omniApplyActivation.value((
    transactionId: 1,
    transaction: (lane: "snapshot", generation: 2),
    definitions: activationDefinitions,
    roots: [],
    effectiveBeat: 0.5
));
if(~omniDefinitions["snapshot/child"][\revision] != 2) {
    Error("new definition was not published at activation").throw;
};
~omniStartFinite.value("snapshot/child", "parent-b", 0.5);
revisions = ~omniExecutions.values.collect {
    |execution| execution[\definition][\revision]
}.sort;
if(revisions != [1, 2]) {
    Error("running finite execution did not retain its snapshot").throw;
};

~omniPendingActivations.clear;
queued = { |transactionId, lane, generation, beat| (
    transactionId: transactionId,
    transaction: (lane: lane, generation: generation),
    definitions: Dictionary.new,
    roots: [],
    effectiveBeat: beat
) };
if(~omniQueueActivation.value(queued.value(10, "bass", 1, 4)).not) {
    Error("first aligned activation was not queued").throw;
};
~omniQueueActivation.value(queued.value(11, "drums", 1, 4));
~omniQueueActivation.value(queued.value(12, "bass", 1, 8));
if(~omniQueueActivation.value(queued.value(13, "bass", 2, 4)).not) {
    Error("newer same-boundary activation was not queued").throw;
};
if(~omniPendingActivations.size != 3) {
    Error("same-lane replacement disturbed an independent boundary").throw;
};
if(~omniPendingActivations.any { |item| item[\transactionId] == 10 }) {
    Error("superseded aligned activation remained queued").throw;
};
if(~omniTransactionResults[10][\code] != "replaced-before-activation") {
    Error("superseded activation result was not retained").throw;
};
if(~omniQueueActivation.value(queued.value(14, "bass", 1, 4))) {
    Error("obsolete out-of-order generation replaced a newer activation").throw;
};
if(~omniPendingActivations.any { |item| item[\transactionId] == 14 }) {
    Error("obsolete generation was queued").throw;
};

"LB_OMNICHORD_SC_SEQUENCER_SNAPSHOT_OK".postln;
0.exit;
)
