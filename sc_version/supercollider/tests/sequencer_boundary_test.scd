/* External/nested boundary, tempo-domain and stale-callback contracts. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;
var releases = List.new;
var child;
var root;
var transaction;
var activation;
var nested;
var dueSlow;
var dueFast;

~omniLanguagePort = 57149;
~omniClientSession = "boundary-test";
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
/* Prevent this deterministic state test from scheduling a real clock wake. */
~omniArmWake = { };

child = (
    id: "boundary/child", revision: 1, kind: "finite", lane: "boundary",
    period: 0, eventCount: 1,
    events: [(
        type: \event, definitionId: "boundary/child", tick: 48, ordinal: 0,
        action: "noteOff", atoms: ["held", 0.0]
    )]
);
root = (
    id: "boundary/root", revision: 1, kind: "root", lane: "boundary",
    period: 48, eventCount: 1,
    events: [(
        type: \event, definitionId: "boundary/root", tick: 0, ordinal: 0,
        action: "launch", atoms: ["boundary/child"]
    )]
);

/* An external transaction at an exact beat still advances one tick before
 * applying its alignment. At beat 1 with bar alignment this means beat 2. */
~omniTransportRunning = true;
~omniClock.beats = 1;
transaction = (
    lane: "boundary", generation: 1, count: 4,
    applyMode: "replace", alignment: 48,
    records: [
        (
            type: \definition, id: root[\id], revision: 1, kind: "root",
            period: 48, eventCount: 1
        ),
        root[\events][0],
        (
            type: \definition, id: child[\id], revision: 1, kind: "finite",
            period: 0, eventCount: 1
        ),
        child[\events][0]
    ]
);
~omniPublishTransaction.value(transaction, 90);
activation = ~omniPendingActivations.detect { |item|
    item[\transactionId] == 90
};
if(activation.isNil or: {
    (activation[\effectiveBeat] - 2).abs > 0.0000001
}) {
    Error("external exact-boundary activation did not use next-tick rule").throw;
};

/* A nested launch uses its current logical beat and introduces no extra tick. */
~omniDefinitions[child[\id]] = child;
~omniDefinitions[root[\id]] = root;
~omniExecutions.clear;
~omniStartRoot.value(root, "boundary", 1, 3.25);
~omniRunSequenceEvent.value(
    root[\events][0], ~omniExecutions.values.detect(_.at(\root)), 3.25
);
nested = ~omniExecutions.values.detect { |item| item[\root].not };
if(nested.isNil or: { (nested[\baseBeat] - 3.25).abs > 0.0000001 }) {
    Error("nested launch inserted an extra timing tick").throw;
};

/* Release beats live in the TempoClock beat domain, not precomputed seconds. */
~omniClock.tempo = 1;
dueSlow = ~omniExecutionDueBeat.value(nested);
~omniClock.tempo = 4;
dueFast = ~omniExecutionDueBeat.value(nested);
if((dueSlow - 4.25).abs > 0.0000001 or: {
    (dueFast - dueSlow).abs > 0.0000001
}) {
    Error("tempo change moved a sequenced release beat").throw;
};

/* Gates never consume explicit releases. The final event executes before the
 * finite execution is retired. */
~omniGates["owner"] = Dictionary[
    "hold" -> (untilTick: 999, scope: "noteOn")
];
~omniRunSequenceEvent.value(child[\events][0], nested, dueFast);
~omniAdvanceExecution.value(nested);
if(releases.asArray != [nested[\id] ++ "/held"]) {
    Error("gate suppressed or duplicated an exact note release").throw;
};
if(~omniExecutions[nested[\id]].notNil) {
    Error("finite execution remained after its final release").throw;
};

/* Panic/epoch invalidation makes an already scheduled wake ticket harmless. */
~omniExecutions.clear;
~omniStartFinite.value(child[\id], "stale-parent", 0);
~omniWakeTicket = 8;
~omniWake.value(7, 1);
if(releases.size != 1) {
    Error("stale wake executed after ticket invalidation").throw;
};

"LB_OMNICHORD_SC_SEQUENCER_BOUNDARY_OK".postln;
0.exit;
)
