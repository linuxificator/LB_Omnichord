/* Native LB Omnichord sequence transaction and TempoClock coordinator. */

~omniTransactions = IdentityDictionary.new;
~omniTransactionResults = IdentityDictionary.new;
~omniDefinitions = Dictionary.new;
~omniLanes = Dictionary.new;
~omniGates = Dictionary.new;
~omniExecutions = Dictionary.new;
~omniExecutionOrdinal = 0;
~omniMaxTransactions = 64;
~omniMaxTransactionRecords = 20000;
~omniMaxExecutions = 256;

~omniEventValidationError = { |action, atoms|
    var expected = Dictionary[
        "launch" -> 1,
        "gateBegin" -> 4,
        "rootStop" -> 1,
        "rootStart" -> 1,
        "noteOn" -> 10,
        "noteOff" -> 2,
        "voiceSet" -> 3,
        "drumHit" -> 5
    ];
    var count = expected[action];
    var error = nil;
    if(count.isNil) {
        error = "invalid-event-action";
    } {
        if(atoms.size != count) { error = "invalid-event-payload-size" };
    };
    if(error.isNil and: { action == "gateBegin" }) {
        if(atoms[2].isNumber.not or: { atoms[2].asInteger <= 0 }) {
            error = "gate-duration-must-be-positive";
        };
        if(["drumHit", "launch", "noteOn"].includesEqual(
            atoms[3].asString
        ).not) {
            error = "invalid-gate-scope";
        };
    };
    if(error.isNil and: { action == "noteOn" }) {
        if(atoms[3].isNumber.not or: { atoms[3].asInteger <= 0 }) {
            error = "invalid-program-revision";
        };
        if(atoms[4].isNumber.not or: {
            atoms[4].asInteger < 0 or: { atoms[4].asInteger > 127 }
        }) { error = "invalid-logical-key" };
        if(atoms[5].isNumber.not or: { atoms[5].asFloat <= 0 }) {
            error = "invalid-note-frequency";
        };
        if(atoms[6].isNumber.not or: {
            atoms[6].asFloat < 0 or: { atoms[6].asFloat > 1 }
        }) { error = "invalid-note-velocity" };
        if(atoms[8].isNumber.not or: {
            [0, 1].includesEqual(atoms[8].asInteger).not
        }) { error = "invalid-note-accent" };
        if(atoms[9].isNumber.not or: {
            atoms[9].asInteger < 0 or: { atoms[9].asInteger > 10 }
        }) { error = "invalid-logical-bus" };
    };
    if(error.isNil and: { action == "noteOff" }) {
        if(atoms[1].isNumber.not or: {
            atoms[1].asFloat < 0 or: { atoms[1].asFloat > 1 }
        }) { error = "invalid-release-velocity" };
    };
    if(error.isNil and: { action == "voiceSet" }) {
        if(atoms[2].isNumber.not) { error = "invalid-voice-value" };
    };
    if(error.isNil and: { action == "drumHit" }) {
        if(atoms[2].isNumber.not or: {
            atoms[2].asInteger < 0 or: { atoms[2].asInteger > 127 }
        }) { error = "invalid-drum-key" };
        if(atoms[3].isNumber.not or: {
            atoms[3].asFloat < 0 or: { atoms[3].asFloat > 1 }
        }) { error = "invalid-drum-velocity" };
        if(atoms[4].isNumber.not or: {
            atoms[4].asInteger < 0 or: { atoms[4].asInteger > 10 }
        }) { error = "invalid-logical-bus" };
    };
    error
};

~omniAck = { |transactionId, stage, generation, effectiveBeat, code|
    if(~omniReplyAddress.notNil) {
        ~omniReply.value(
            ~omniReplyAddress,
            '/omni/v1/ack',
            ~omniClientSession,
            transactionId,
            stage,
            generation,
            effectiveBeat,
            code
        );
    };
};

~omniStopLane = { |lane|
    var old = ~omniLanes[lane];
    if(old.notNil) {
        old[\routines].do { |routine| routine.stop };
        old[\routines].clear;
    };
};

~omniRunSequenceEvent = {
    |event, executionId, isRoot, rootLane, rootGeneration|
    var action = event[\action];
    var atoms = event[\atoms];
    var validRoot = isRoot.not or: {
        var laneState = ~omniLanes[rootLane];
        laneState.notNil and: { laneState[\generation] == rootGeneration };
    };
    if(validRoot) {
        if(action == "launch") {
            ~omniStartFinite.value(atoms[0].asString, executionId);
        };
        if(action == "gateBegin") {
            var untilTick = (~omniClock.beats * 48).floor + atoms[2].asInteger;
            ~omniGates[atoms[0].asString] = untilTick;
        };
        if(action == "noteOn") {
            var handle = executionId ++ "/" ++ atoms[0].asString;
            ~omniSpawnVoice.value(
                atoms[1], handle, atoms[2], atoms[3], atoms[4],
                atoms[5], atoms[6], atoms[9], [
                    \articulation, atoms[7],
                    \accent, atoms[8]
                ]
            );
        };
        if(action == "noteOff") {
            ~omniReleaseHandle.value(executionId ++ "/" ++ atoms[0].asString);
        };
        if(action == "voiceSet") {
            ~omniSetHandle.value(
                executionId ++ "/" ++ atoms[0].asString,
                atoms[1].asString,
                atoms[2]
            );
        };
        if(action == "drumHit") {
            var role = atoms[0].asString;
            var gateUntil = ~omniGates[role] ? -1;
            var nowTick = (~omniClock.beats * 48).floor;
            if(isRoot.not or: { nowTick >= gateUntil }) {
                ~omniSpawnDrum.value(atoms[1], atoms[2], atoms[3], atoms[4]);
            };
        };
    };
};

~omniScheduleDefinition = {
    |definition, executionId, baseBeat, isRoot, rootLane, rootGeneration|
    definition[\events].do { |event|
        ~omniClock.schedAbs(baseBeat + (event[\tick] / 48), {
            ~omniRunSequenceEvent.value(
                event, executionId, isRoot, rootLane, rootGeneration
            );
            nil
        });
    };
};

~omniStartFinite = { |definitionId, parentExecution|
    var definition = ~omniDefinitions[definitionId];
    if(~omniExecutions.size >= ~omniMaxExecutions) {
        ("LB_OMNICHORD_SC_EXECUTION_LIMIT definition=" ++ definitionId).warn;
    } {
    if(definition.notNil and: { definition[\kind] == "finite" }) {
        var executionId;
        var endTick = definition[\events].collect { |event| event[\tick] }.maxItem ? 0;
        ~omniExecutionOrdinal = ~omniExecutionOrdinal + 1;
        executionId = parentExecution ++ "/" ++ ~omniExecutionOrdinal;
        ~omniExecutions[executionId] = definitionId;
        ~omniScheduleDefinition.value(
            definition, executionId, ~omniClock.beats, false, "", 0
        );
        ~omniClock.sched(endTick / 48, {
            ~omniExecutions.removeAt(executionId);
            nil
        });
    };
    };
};

~omniStartRoot = { |definition, lane, generation, startBeat|
    var routine = Routine({
        var cycle = 0;
        var period = definition[\period].asInteger / 48;
        (startBeat - ~omniClock.beats).max(0).wait;
        loop {
            var baseBeat = startBeat + (cycle * period);
            var executionId = lane ++ "/" ++ generation ++ "/" ++ cycle;
            ~omniScheduleDefinition.value(
                definition, executionId, baseBeat, true, lane, generation
            );
            cycle = cycle + 1;
            period.wait;
        };
    });
    routine.play(~omniClock);
    routine
};

~omniActivateLane = { |lane, generation, definitionIds, effectiveBeat|
    var routines = List.new;
    ~omniStopLane.value(lane);
    ~omniLanes[lane] = (
        generation: generation,
        definitionIds: definitionIds,
        routines: routines
    );
    if(~omniTransportRunning) {
        definitionIds.do { |definitionId|
            var definition = ~omniDefinitions[definitionId];
            if(definition.notNil and: { definition[\kind] == "root" }) {
                routines.add(
                    ~omniStartRoot.value(definition, lane, generation, effectiveBeat)
                );
            };
        };
    };
};

~omniPublishTransaction = { |transaction, transactionId|
    var definitions = Dictionary.new;
    var roots = List.new;
    var rejected = nil;
    transaction[\records].do { |record|
        if(record[\type] == \definition) {
            if(definitions[record[\id]].notNil) {
                rejected = "duplicate-definition-id";
            } {
                definitions[record[\id]] = (
                    id: record[\id],
                    revision: record[\revision],
                    kind: record[\kind],
                    period: record[\period],
                    eventCount: record[\eventCount],
                    events: List.new
                );
            };
            if(["root", "finite"].includesEqual(record[\kind]).not) {
                rejected = "invalid-definition-kind";
            };
            if((record[\kind] == "root") and: { record[\period] <= 0 }) {
                rejected = "root-period-must-be-positive";
            };
            if((record[\kind] == "finite") and: { record[\period] != 0 }) {
                rejected = "finite-period-must-be-zero";
            };
            if(record[\kind] == "root") { roots.add(record[\id]) };
        };
    };
    transaction[\records].do { |record|
        if(record[\type] == \event) {
            var definition = definitions[record[\definitionId]];
            if(definition.isNil) {
                rejected = "event-references-missing-definition";
            } {
                definition[\events].add(record);
                if(record[\tick] < 0 or: { record[\ordinal] < 0 }) {
                    rejected = "negative-event-position";
                };
                if([
                    "launch", "gateBegin", "rootStop", "rootStart",
                    "noteOn", "noteOff", "voiceSet", "drumHit"
                ].includesEqual(record[\action]).not) {
                    rejected = "invalid-event-action";
                };
                if(~omniEventValidationError.value(
                    record[\action], record[\atoms]
                ).notNil) {
                    rejected = ~omniEventValidationError.value(
                        record[\action], record[\atoms]
                    );
                };
            };
        };
    };
    definitions.keysValuesDo { |id, definition|
        definition[\events] = definition[\events].asArray.sort { |left, right|
            if(left[\tick] == right[\tick]) {
                left[\ordinal] < right[\ordinal]
            } {
                left[\tick] < right[\tick]
            }
        };
        if(definition[\events].size != definition[\eventCount]) {
            rejected = "definition-event-count-mismatch";
        };
        definition[\events].do { |event|
            if(event[\action] == "launch") {
                var target = definitions[event[\atoms][0].asString];
                if(target.isNil) {
                    rejected = "launch-references-missing-definition";
                } {
                    if(definition[\kind] != "root") {
                        rejected = "finite-definition-cannot-launch";
                    };
                    if(target[\kind] != "finite") {
                        rejected = "launch-target-must-be-finite";
                    };
                };
            };
            if(["rootStop", "rootStart"].includesEqual(event[\action])) {
                var target = definitions[event[\atoms][0].asString];
                if(target.isNil or: { target[\kind] != "root" }) {
                    rejected = "root-control-target-must-be-root";
                };
            };
        };
    };
    if(rejected.notNil) {
        ~omniTransactionResults[transactionId] = (
            stage: "rejected", generation: transaction[\generation],
            beat: ~omniClock.beats, code: rejected
        );
        ~omniAck.value(
            transactionId, "rejected", transaction[\generation],
            ~omniClock.beats, rejected
        );
    } {
        definitions.keysValuesDo { |id, definition| ~omniDefinitions[id] = definition };
        if(~omniTransportRunning) {
            var nextTick = (~omniClock.beats * 48).floor + 1;
            var alignment = transaction[\alignment].max(1);
            var effectiveTick = ((nextTick + alignment - 1) / alignment).floor * alignment;
            var effectiveBeat = effectiveTick / 48;
            ~omniTransactionResults[transactionId] = (
                stage: "scheduled", generation: transaction[\generation],
                beat: effectiveBeat, code: "ok"
            );
            ~omniAck.value(
                transactionId, "scheduled", transaction[\generation], effectiveBeat, "ok"
            );
            ~omniClock.schedAbs(effectiveBeat, {
                var current = ~omniLanes[transaction[\lane]];
                if(current.notNil and: {
                    current[\generation] > transaction[\generation]
                }) {
                    ~omniTransactionResults[transactionId] = (
                        stage: "applied", generation: transaction[\generation],
                        beat: effectiveBeat, code: "obsolete-generation"
                    );
                    ~omniAck.value(
                        transactionId, "applied", transaction[\generation],
                        effectiveBeat, "obsolete-generation"
                    );
                } {
                    ~omniActivateLane.value(
                        transaction[\lane], transaction[\generation], roots, effectiveBeat
                    );
                    ~omniTransactionResults[transactionId] = (
                        stage: "applied", generation: transaction[\generation],
                        beat: effectiveBeat, code: "ok"
                    );
                    ~omniAck.value(
                        transactionId, "applied", transaction[\generation],
                        effectiveBeat, "ok"
                    );
                };
                nil
            });
        } {
            ~omniActivateLane.value(
                transaction[\lane], transaction[\generation], roots, ~omniClock.beats
            );
            ~omniTransactionResults[transactionId] = (
                stage: "applied", generation: transaction[\generation],
                beat: ~omniClock.beats, code: "ok"
            );
            ~omniAck.value(
                transactionId, "applied", transaction[\generation],
                ~omniClock.beats, "ok"
            );
        };
    };
};

OSCdef(\omniTxBegin, { |message|
    if(~omniSessionValid.value(message)) {
        var transactionId = message[2].asInteger;
        var result = ~omniTransactionResults[transactionId];
        if(result.notNil) {
            ~omniAck.value(
                transactionId, result[\stage], result[\generation],
                result[\beat], result[\code]
            );
        } {
            var count = message[5].asInteger;
            if(count < 0 or: { count > ~omniMaxTransactionRecords }) {
                ~omniAck.value(
                    transactionId, "rejected", message[4].asInteger,
                    ~omniClock.beats, "transaction-size-out-of-range"
                );
            } {
            if(~omniTransactions.size >= ~omniMaxTransactions) {
                ~omniAck.value(
                    transactionId, "rejected", message[4].asInteger,
                    ~omniClock.beats, "too-many-open-transactions"
                );
            } {
            ~omniTransactions[transactionId] = (
                lane: message[3].asString,
                generation: message[4].asInteger,
                count: count,
                applyMode: message[6].asString,
                alignment: message[7].asInteger,
                records: Array.newClear(count),
                rejected: nil
            );
            };
            };
        };
    };
}, '/omni/v1/tx/begin', recvPort: ~omniLanguagePort);

~omniStoreRecord = { |transactionId, packetIndex, record|
    var transaction = ~omniTransactions[transactionId];
    if(transaction.notNil) {
        if(packetIndex < 0 or: { packetIndex >= transaction[\count] }) {
            transaction[\rejected] = "packet-index-out-of-range";
        } {
            var previous = transaction[\records][packetIndex];
            if(previous.isNil) {
                transaction[\records][packetIndex] = record;
            } {
                if(previous.asCompileString != record.asCompileString) {
                    transaction[\rejected] = "conflicting-duplicate-packet";
                };
            };
        };
    };
};

OSCdef(\omniTxDefinition, { |message|
    if(~omniSessionValid.value(message)) {
        ~omniStoreRecord.value(
            message[2].asInteger,
            message[3].asInteger,
            (
                type: \definition, id: message[4].asString,
                revision: message[5].asInteger, kind: message[6].asString,
                period: message[7].asInteger, eventCount: message[8].asInteger
            )
        );
    };
}, '/omni/v1/tx/def', recvPort: ~omniLanguagePort);

OSCdef(\omniTxEvent, { |message|
    if(~omniSessionValid.value(message)) {
        ~omniStoreRecord.value(
            message[2].asInteger,
            message[3].asInteger,
            (
                type: \event, definitionId: message[4].asString,
                tick: message[5].asInteger, ordinal: message[6].asInteger,
                action: message[7].asString, atoms: message[8..]
            )
        );
    };
}, '/omni/v1/tx/event', recvPort: ~omniLanguagePort);

OSCdef(\omniTxCommit, { |message|
    if(~omniSessionValid.value(message)) {
        var transactionId = message[2].asInteger;
        var transaction = ~omniTransactions[transactionId];
        if(transaction.notNil) {
            if(transaction[\rejected].notNil) {
                ~omniAck.value(
                    transactionId, "rejected", transaction[\generation],
                    ~omniClock.beats, transaction[\rejected]
                );
            } {
                if(transaction[\records].any(_.isNil)) {
                    ~omniAck.value(
                        transactionId, "rejected", transaction[\generation],
                        ~omniClock.beats, "incomplete"
                    );
                } {
                    ~omniPublishTransaction.value(transaction, transactionId);
                    ~omniTransactions.removeAt(transactionId);
                };
            };
        };
    };
}, '/omni/v1/tx/commit', recvPort: ~omniLanguagePort);

OSCdef(\omniTransport, { |message|
    if(~omniSessionValid.value(message)) {
        var action = message[3].asString;
        ~omniClock.tempo = message[4].asFloat.max(1) / 60;
        if(action == "start") {
            ~omniTransportEpoch = ~omniTransportEpoch + 1;
            ~omniClock.clear;
            ~omniClock.beats = 0;
            ~omniTransportRunning = true;
            ~omniLanes.keysValuesDo { |lane, state|
                ~omniActivateLane.value(
                    lane, state[\generation], state[\definitionIds], 0
                );
            };
        };
        if((action == "stop") or: { action == "panic" }) {
            ~omniLanes.keys.do { |lane| ~omniStopLane.value(lane) };
            ~omniClock.clear;
            ~omniTransportRunning = false;
            ~omniPanic.value;
        };
    };
}, '/omni/v1/transport', recvPort: ~omniLanguagePort);
