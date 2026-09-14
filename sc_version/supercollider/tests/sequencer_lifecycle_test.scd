/* Root/finite execution ownership and release behavior; no audio server. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var releases = List.new;
var finiteEvent = (
    type: \event,
    definitionId: "lifecycle/child",
    tick: 48,
    ordinal: 0,
    action: "noteOff",
    atoms: ["held", 0.0]
);
var child = (
    id: "lifecycle/child",
    revision: 1,
    kind: "finite",
    lane: "lifecycle",
    period: 0,
    eventCount: 1,
    events: [finiteEvent]
);
var root = (
    id: "lifecycle/root",
    revision: 1,
    kind: "root",
    lane: "lifecycle",
    period: 48,
    eventCount: 1,
    events: [(
        type: \event,
        definitionId: "lifecycle/root",
        tick: 0,
        ordinal: 0,
        action: "launch",
        atoms: ["lifecycle/child"]
    )]
);
var finiteExecutions;
var chosenExecution;

~omniLanguagePort = 57149;
~omniClientSession = "lifecycle-test";
~omniReplyAddress = nil;
~omniClock = TempoClock.new(2);
~omniTransportEpoch = 0;
~omniTransportRunning = false;
~omniReply = { };
~omniSessionValid = { false };
~omniReleaseHandle = { |handle| releases.add(handle.asString) };
~omniSetHandle = { };
~omniPanic = { };
~omniSpawnVoice = { };
~omniSpawnDrum = { };

(directory +/+ "sequencer.scd").load;
~omniDefinitions[child[\id]] = child;
~omniDefinitions[root[\id]] = root;

~omniStartFinite.value(child[\id], "parent-a", 0);
~omniStartFinite.value(child[\id], "parent-b", 0);
finiteExecutions = ~omniExecutions.values.select { |item| item[\root].not };
if(finiteExecutions.size != 2) {
    Error("overlapping finite launches did not retain two executions").throw;
};
if(finiteExecutions.collect(_.at(\id)).asSet.size != 2) {
    Error("overlapping finite launches reused an execution identity").throw;
};

~omniStartRoot.value(root, "lifecycle", 1, 0);
if(~omniExecutions.values.count(_.at(\root)) != 1) {
    Error("root execution was not created").throw;
};
~omniRemoveRootExecutions.value("lifecycle", root[\id]);
if(~omniExecutions.values.count(_.at(\root)) != 0) {
    Error("root stop left the root running").throw;
};
finiteExecutions = ~omniExecutions.values.select { |item| item[\root].not };
if(finiteExecutions.size != 2) {
    Error("root stop incorrectly destroyed finite children").throw;
};

chosenExecution = finiteExecutions.detect { |item|
    item[\id].asString.beginsWith("parent-a/")
};
~omniRunSequenceEvent.value(
    chosenExecution[\definition][\events][0], chosenExecution, 1
);
if(releases.asArray != [chosenExecution[\id] ++ "/held"]) {
    Error("finite child release did not use its exact execution handle").throw;
};

~omniGates["target"] = Dictionary[
    "short" -> (untilTick: 1, scope: "noteOn"),
    "long" -> (untilTick: 2, scope: "noteOn")
];
if(~omniGateActive.value("target", "noteOn", 0).not) {
    Error("overlapping gates were not active at their start").throw;
};
if(~omniGateActive.value("target", "noteOn", 1).not) {
    Error("expiring one gate incorrectly removed the other gate").throw;
};
if(~omniGateActive.value("target", "noteOn", 2)) {
    Error("gate remained active at its half-open end boundary").throw;
};

"LB_OMNICHORD_SC_SEQUENCER_LIFECYCLE_OK".postln;
0.exit;
)
