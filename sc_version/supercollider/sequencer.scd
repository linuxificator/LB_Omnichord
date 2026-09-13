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
~omniMaxSameBeatActions = 4096;
~omniWakeTicket = 0;
~omniWakeBeat = nil;
~omniPendingActivations = List.new;
~omniTransactionResultOrder = List.new;
~omniMaxTransactionResults = 256;
~omniTransactionTimeoutSeconds = 5;

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

~omniStoreTransactionResult = {
    |transactionId, stage, generation, effectiveBeat, code|
    if(~omniTransactionResults[transactionId].isNil) {
        ~omniTransactionResultOrder.add(transactionId);
    };
    ~omniTransactionResults[transactionId] = (
        stage: stage, generation: generation, beat: effectiveBeat, code: code
    );
    while { ~omniTransactionResultOrder.size > ~omniMaxTransactionResults } {
        ~omniTransactionResults.removeAt(~omniTransactionResultOrder.removeAt(0));
    };
};

~omniPruneTransactions = {
    var now = Main.elapsedTime;
    var expired = List.new;
    ~omniTransactions.keysValuesDo { |transactionId, transaction|
        if((now - transaction[\createdAt]) > ~omniTransactionTimeoutSeconds) {
            expired.add(transactionId);
        };
    };
    expired.do { |transactionId| ~omniTransactions.removeAt(transactionId) };
};

~omniActionPhase = { |action|
    if(["gateBegin", "rootStop", "rootStart"].includesEqual(action)) { 0 } {
        if(action == "launch") { 1 } {
            if(action == "noteOff") { 2 } {
                if(action == "voiceSet") { 3 } { 4 }
            }
        }
    }
};

~omniExecutionDueBeat = { |execution|
    var events = execution[\definition][\events];
    var index = execution[\nextIndex];
    if(index < events.size) {
        execution[\baseBeat] + (events[index][\tick] / 48)
    } { nil }
};

~omniInvalidateWake = {
    ~omniWakeTicket = ~omniWakeTicket + 1;
    ~omniWakeBeat = nil;
};

~omniRemoveRootExecutions = { |lane, definitionId|
    var remove = List.new;
    ~omniExecutions.keysValuesDo { |executionId, execution|
        if(execution[\root] and: {
            (lane.isNil or: { execution[\lane] == lane }) and: {
                definitionId.isNil or: {
                    execution[\definition][\id] == definitionId
                }
            }
        }) { remove.add(executionId) };
    };
    remove.do { |executionId| ~omniExecutions.removeAt(executionId) };
};

~omniStopLane = { |lane|
    ~omniRemoveRootExecutions.value(lane.asString, nil);
};

~omniGateActive = { |target, scope, logicalTick|
    var causes = ~omniGates[target.asString];
    var expired = List.new;
    var active = false;
    if(causes.notNil) {
        causes.keysValuesDo { |token, cause|
            if(cause[\untilTick] <= logicalTick) {
                expired.add(token);
            } {
                if(cause[\scope] == scope.asString) { active = true };
            };
        };
        expired.do { |token| causes.removeAt(token) };
        if(causes.isEmpty) { ~omniGates.removeAt(target.asString) };
    };
    active
};

~omniStartRoot = { |definition, lane, generation, startBeat|
    var executionId;
    if(definition[\events].notEmpty) {
        ~omniExecutionOrdinal = ~omniExecutionOrdinal + 1;
        executionId = "root/" ++ lane ++ "/" ++ ~omniExecutionOrdinal;
        ~omniExecutions[executionId] = (
            id: executionId,
            definition: definition,
            lane: lane.asString,
            generation: generation.asInteger,
            root: true,
            baseBeat: startBeat,
            nextIndex: 0,
            creationOrdinal: ~omniExecutionOrdinal
        );
    };
    executionId
};

~omniStartFinite = { |definitionId, parentExecution, startBeat|
    var definition = ~omniDefinitions[definitionId.asString];
    var finiteCount = ~omniExecutions.values.select {
        |item| item[\root].not
    }.size;
    if(finiteCount >= ~omniMaxExecutions) {
        ("LB_OMNICHORD_SC_EXECUTION_LIMIT definition=" ++ definitionId).warn;
    } {
        if(definition.notNil and: {
            definition[\kind] == "finite" and: { definition[\events].notEmpty }
        }) {
            var executionId;
            ~omniExecutionOrdinal = ~omniExecutionOrdinal + 1;
            executionId = parentExecution ++ "/" ++ ~omniExecutionOrdinal;
            ~omniExecutions[executionId] = (
                id: executionId,
                definition: definition,
                lane: definition[\lane],
                generation: definition[\revision],
                root: false,
                baseBeat: startBeat,
                nextIndex: 0,
                creationOrdinal: ~omniExecutionOrdinal
            );
        };
    };
};

~omniStartNamedRoot = { |definitionId, startBeat|
    var definition = ~omniDefinitions[definitionId.asString];
    if(definition.notNil and: { definition[\kind] == "root" }) {
        var lane = definition[\lane];
        var state = ~omniLanes[lane];
        if(state.notNil and: {
            state[\definitionIds].includesEqual(definitionId.asString)
        }) {
            ~omniStartRoot.value(
                definition, lane, state[\generation], startBeat
            );
        };
    };
};

~omniRunSequenceEvent = { |event, execution, dueBeat|
    var action = event[\action];
    var atoms = event[\atoms];
    var executionId = execution[\id];
    var logicalTick = (dueBeat * 48).round.asInteger;
    var suppressed = false;
    if(action == "gateBegin") {
        var target = atoms[0].asString;
        var causes = ~omniGates[target];
        if(causes.isNil) {
            causes = Dictionary.new;
            ~omniGates[target] = causes;
        };
        causes[atoms[1].asString] = (
            untilTick: logicalTick + atoms[2].asInteger,
            scope: atoms[3].asString
        );
    };
    if(action == "rootStop") {
        ~omniRemoveRootExecutions.value(nil, atoms[0].asString);
    };
    if(action == "rootStart") {
        ~omniStartNamedRoot.value(atoms[0].asString, dueBeat);
    };
    if(action == "launch") {
        suppressed = ~omniGateActive.value(
            atoms[0].asString, "launch", logicalTick
        );
        if(suppressed.not) {
            ~omniStartFinite.value(atoms[0].asString, executionId, dueBeat);
        };
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
    if(action == "noteOn") {
        suppressed = ~omniGateActive.value(
            atoms[1].asString, "noteOn", logicalTick
        );
        if(suppressed.not) {
            ~omniSpawnVoice.value(
                atoms[1], executionId ++ "/" ++ atoms[0].asString,
                atoms[2], atoms[3], atoms[4], atoms[5], atoms[6], atoms[9],
                [\articulation, atoms[7], \accent, atoms[8]]
            );
        };
    };
    if(action == "drumHit") {
        suppressed = execution[\root] and: {
            ~omniGateActive.value(atoms[0], "drumHit", logicalTick)
        };
        if(suppressed.not) {
            ~omniSpawnDrum.value(
                atoms[0], atoms[1], atoms[2], atoms[3], atoms[4]
            );
        };
    };
    if(~omniTraceSequenceEvent.notNil) {
        ~omniTraceSequenceEvent.value(
            logicalTick, executionId, execution[\definition][\id],
            execution[\definition][\revision], event[\ordinal],
            action, suppressed
        );
    };
};

~omniAdvanceExecution = { |execution|
    if(~omniExecutions[execution[\id]] === execution) {
        execution[\nextIndex] = execution[\nextIndex] + 1;
        if(execution[\nextIndex] >= execution[\definition][\events].size) {
            if(execution[\root]) {
                execution[\nextIndex] = 0;
                execution[\baseBeat] = execution[\baseBeat]
                    + (execution[\definition][\period] / 48);
            } {
                ~omniExecutions.removeAt(execution[\id]);
            };
        };
    };
};

~omniDueItems = { |dueBeat|
    var items = List.new;
    ~omniExecutions.keysValuesDo { |executionId, execution|
        var beat = ~omniExecutionDueBeat.value(execution);
        if(beat.notNil and: { beat <= (dueBeat + 0.0000001) }) {
            var event = execution[\definition][\events][execution[\nextIndex]];
            items.add((
                beat: beat,
                phase: ~omniActionPhase.value(event[\action]),
                creation: execution[\creationOrdinal],
                ordinal: event[\ordinal],
                event: event,
                execution: execution
            ));
        };
    };
    items.asArray.sort { |left, right|
        if(left[\beat] != right[\beat]) { left[\beat] < right[\beat] } {
            if(left[\phase] != right[\phase]) {
                left[\phase] < right[\phase]
            } {
                if(left[\creation] != right[\creation]) {
                    left[\creation] < right[\creation]
                } { left[\ordinal] < right[\ordinal] }
            }
        }
    }
};

~omniWake = { |ticket, dueBeat|
    var processed = 0;
    var due;
    if(ticket == ~omniWakeTicket) {
        ~omniWakeBeat = nil;
        ~omniApplyDueActivations.value(dueBeat);
        while {
            due = ~omniDueItems.value(dueBeat);
            due.notEmpty and: { processed < ~omniMaxSameBeatActions }
        } {
            var item = due[0];
            ~omniRunSequenceEvent.value(
                item[\event], item[\execution], item[\beat]
            );
            ~omniAdvanceExecution.value(item[\execution]);
            processed = processed + 1;
        };
        if(processed >= ~omniMaxSameBeatActions) {
            "LB_OMNICHORD_SC_SAME_BEAT_LIMIT".warn;
        };
        ~omniArmWake.value;
    };
    nil
};

~omniArmWake = {
    var beats = ~omniExecutions.values.collect { |execution|
        ~omniExecutionDueBeat.value(execution)
    }.reject(_.isNil);
    beats = beats ++ ~omniPendingActivations.collect { |item|
        item[\effectiveBeat]
    };
    if(~omniTransportRunning and: { beats.notEmpty }) {
        var beat = beats.minItem;
        if(~omniWakeBeat.isNil or: { beat < (~omniWakeBeat - 0.0000001) }) {
            var ticket;
            ~omniWakeTicket = ~omniWakeTicket + 1;
            ticket = ~omniWakeTicket;
            ~omniWakeBeat = beat;
            ~omniClock.schedAbs(beat, {
                ~omniWake.value(ticket, beat)
            });
        };
    };
};

~omniActivateLane = { |lane, generation, definitionIds, effectiveBeat|
    ~omniStopLane.value(lane);
    ~omniLanes[lane] = (
        generation: generation,
        definitionIds: definitionIds
    );
    if(~omniTransportRunning) {
        definitionIds.do { |definitionId|
            var definition = ~omniDefinitions[definitionId];
            if(definition.notNil and: { definition[\kind] == "root" }) {
                ~omniStartRoot.value(definition, lane, generation, effectiveBeat);
            };
        };
        ~omniArmWake.value;
    };
};

~omniApplyActivation = { |activation|
    var transactionId = activation[\transactionId];
    var transaction = activation[\transaction];
    var effectiveBeat = activation[\effectiveBeat];
    var current = ~omniLanes[transaction[\lane]];
    var code = "ok";
    if(current.notNil and: {
        current[\generation] > transaction[\generation]
    }) {
        code = "obsolete-generation";
    } {
        activation[\definitions].keysValuesDo { |id, definition|
            ~omniDefinitions[id] = definition
        };
        ~omniActivateLane.value(
            transaction[\lane], transaction[\generation],
            activation[\roots], effectiveBeat
        );
    };
    ~omniStoreTransactionResult.value(
        transactionId, "applied", transaction[\generation], effectiveBeat, code
    );
    ~omniAck.value(
        transactionId, "applied", transaction[\generation], effectiveBeat, code
    );
};

~omniApplyDueActivations = { |dueBeat|
    var due = ~omniPendingActivations.select { |activation|
        activation[\effectiveBeat] <= (dueBeat + 0.0000001)
    }.sort { |left, right|
        if(left[\effectiveBeat] != right[\effectiveBeat]) {
            left[\effectiveBeat] < right[\effectiveBeat]
        } {
            left[\transaction][\generation] < right[\transaction][\generation]
        }
    };
    due.do { |activation|
        ~omniPendingActivations.remove(activation);
        ~omniApplyActivation.value(activation);
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
                    lane: transaction[\lane],
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
        ~omniStoreTransactionResult.value(
            transactionId, "rejected", transaction[\generation],
            ~omniClock.beats, rejected
        );
        ~omniAck.value(
            transactionId, "rejected", transaction[\generation],
            ~omniClock.beats, rejected
        );
    } {
        if(~omniTransportRunning) {
            var nextTick = (~omniClock.beats * 48).floor + 1;
            var alignment = transaction[\alignment].max(1);
            var effectiveTick = ((nextTick + alignment - 1) / alignment).floor * alignment;
            var effectiveBeat = effectiveTick / 48;
            ~omniStoreTransactionResult.value(
                transactionId, "scheduled", transaction[\generation],
                effectiveBeat, "ok"
            );
            ~omniAck.value(
                transactionId, "scheduled", transaction[\generation], effectiveBeat, "ok"
            );
            ~omniPendingActivations.add((
                transactionId: transactionId,
                transaction: transaction,
                definitions: definitions,
                roots: roots.asArray,
                effectiveBeat: effectiveBeat
            ));
            ~omniArmWake.value;
        } {
            definitions.keysValuesDo { |id, definition|
                ~omniDefinitions[id] = definition
            };
            ~omniActivateLane.value(
                transaction[\lane], transaction[\generation], roots, ~omniClock.beats
            );
            ~omniStoreTransactionResult.value(
                transactionId, "applied", transaction[\generation],
                ~omniClock.beats, "ok"
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
        var existing;
        ~omniPruneTransactions.value;
        existing = ~omniTransactions[transactionId];
        if(result.notNil) {
            ~omniAck.value(
                transactionId, result[\stage], result[\generation],
                result[\beat], result[\code]
            );
        } {
            var count = message[5].asInteger;
            if(existing.notNil) {
                if(
                    existing[\lane] != message[3].asString
                    or: { existing[\generation] != message[4].asInteger }
                    or: { existing[\count] != count }
                    or: { existing[\applyMode] != message[6].asString }
                    or: { existing[\alignment] != message[7].asInteger }
                ) {
                    existing[\rejected] = "conflicting-duplicate-begin";
                };
            } {
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
                rejected: nil,
                createdAt: Main.elapsedTime
            );
            };
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
                ~omniStoreTransactionResult.value(
                    transactionId, "rejected", transaction[\generation],
                    ~omniClock.beats, transaction[\rejected]
                );
                ~omniAck.value(
                    transactionId, "rejected", transaction[\generation],
                    ~omniClock.beats, transaction[\rejected]
                );
            } {
                if(transaction[\records].any(_.isNil)) {
                    ~omniAck.value(
                        transactionId, "received", transaction[\generation],
                        ~omniClock.beats, "incomplete"
                    );
                } {
                    ~omniPublishTransaction.value(transaction, transactionId);
                    ~omniTransactions.removeAt(transactionId);
                };
            };
            if(transaction[\rejected].notNil) {
                ~omniTransactions.removeAt(transactionId);
            };
        };
    };
}, '/omni/v1/tx/commit', recvPort: ~omniLanguagePort);

OSCdef(\omniTransport, { |message|
    if(~omniSessionValid.value(message) and: {
        ~omniAcceptMessageId.isNil or: {
            ~omniAcceptMessageId.value(message[2])
        }
    }) {
        var action = message[3].asString;
        ~omniClock.tempo = message[4].asFloat.max(1) / 60;
        if(action == "start" and: { ~omniTransportRunning.not }) {
            ~omniTransportEpoch = ~omniTransportEpoch + 1;
            ~omniClock.clear;
            ~omniClock.beats = 0;
            ~omniExecutions.clear;
            ~omniGates.clear;
            ~omniInvalidateWake.value;
            ~omniTransportRunning = true;
            ~omniLanes.keysValuesDo { |lane, state|
                ~omniActivateLane.value(
                    lane, state[\generation], state[\definitionIds], 0
                );
            };
        };
        if(action == "stop") {
            ~omniTransportEpoch = ~omniTransportEpoch + 1;
            ~omniClock.clear;
            ~omniExecutions.clear;
            ~omniGates.clear;
            ~omniInvalidateWake.value;
            ~omniTransportRunning = false;
            if(~omniReleaseOwner.notNil) {
                ["rhythm/drums", "rhythm/bass", "rhythm/chords", "omni/drums"]
                    .do(~omniReleaseOwner);
            };
        };
        if(action == "panic") {
            ~omniTransportEpoch = ~omniTransportEpoch + 1;
            ~omniClock.clear;
            ~omniExecutions.clear;
            ~omniGates.clear;
            ~omniInvalidateWake.value;
            ~omniTransportRunning = false;
            ~omniPanic.value;
        };
    };
}, '/omni/v1/transport', recvPort: ~omniLanguagePort);
