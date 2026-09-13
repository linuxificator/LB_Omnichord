/* Bounded live-command replay-window test; no sockets or audio server. */
(
var directory = thisProcess.nowExecutingPath.dirname.dirname;

~omniReady = true;
~omniClientSession = "session-a";
~omniSessionValid = { |message|
    message[1].asString == ~omniClientSession
};
(directory +/+ "protocol_runtime.scd").load;

~omniMaxMessageIds = 3;
if(~omniCommandValid.value(["path", "session-a", 1]).not) {
    Error("first command ID was rejected").throw;
};
if(~omniCommandValid.value(["path", "session-a", 1])) {
    Error("duplicate command ID was accepted").throw;
};
if(~omniCommandValid.value(["path", "other-session", 2])) {
    Error("foreign session command was accepted").throw;
};
[2, 3, 4].do { |messageId|
    if(~omniCommandValid.value(["path", "session-a", messageId]).not) {
        Error("new command ID was rejected").throw;
    };
};
if(~omniMessageIds.size != 3 or: { ~omniMessageIdOrder.size != 3 }) {
    Error("message replay window exceeded its bound").throw;
};
if(~omniCommandValid.value(["path", "session-a", 1]).not) {
    Error("evicted command ID was not admitted as a new live command").throw;
};

"LB_OMNICHORD_SC_PROTOCOL_RUNTIME_OK".postln;
0.exit;
)
