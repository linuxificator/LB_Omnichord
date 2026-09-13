/* Headless transaction receiver used by the cross-process test; no audio. */
(
var port = ("OMNICHORD_SC_PORT".getenv ? "57149").asInteger;
var directory = thisProcess.nowExecutingPath.dirname.dirname;

~omniLanguagePort = port;
~omniClientSession = nil;
~omniReplyAddress = nil;
~omniClock = TempoClock.new(2);
~omniTransportEpoch = 0;
~omniTransportRunning = false;
~omniVoices = IdentityDictionary.new;

~omniReply = { |address, path ... args|
    NetAddr(address.ip, address.port).sendMsg(path, *args);
};
~omniSessionValid = { |message|
    (~omniClientSession.notNil) and: { message[1].asString == ~omniClientSession };
};
~omniReleaseHandle = { |ignoredHandle| ignoredHandle };
~omniSetHandle = { |handle, parameter, value| [handle, parameter, value] };
~omniPanic = { };
~omniSpawnVoice = { |owner, handle, program, revision, logicalKey,
    frequency, velocity, logicalBus, extraArgs|
    [owner, handle, program, revision, logicalKey, frequency,
        velocity, logicalBus, extraArgs]
};
~omniSpawnDrum = { |note, velocity, logicalBus| [note, velocity, logicalBus] };

thisProcess.openUDPPort(port);
(directory +/+ "sequencer.scd").load;

OSCdef(\omniTestHello, { |message, time, address|
    var replyPort = message[3].asInteger;
    ~omniClientSession = message[1].asString;
    ~omniReplyAddress = NetAddr(address.ip, replyPort);
    ~omniReply.value(
        ~omniReplyAddress,
        '/omni/v1/ready',
        "coordinator-test",
        1,
        "test-catalog",
        "ready"
    );
}, '/omni/v1/hello', recvPort: port);

OSCdef(\omniTestShutdown, { |message|
    if(~omniSessionValid.value(message)) { 0.exit };
}, '/omni/v1/shutdown', recvPort: port);

("LB_OMNICHORD_SC_COORDINATOR_READY port=" ++ port).postln;
)
