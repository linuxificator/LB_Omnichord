/* LB routing adapter for the pinned SCLOrkSynths definition. */
SynthDef("pluck", {
    |out=0, amp=0.1, freq=440, decay=5, coef=0.1, pan=0|
    var envelope = EnvGen.kr(Env.linen(0, decay, 0), doneAction: 2);
    var signal = Pluck.ar(
        WhiteNoise.ar(amp),
        Impulse.kr(0),
        0.1,
        freq.reciprocal,
        decay,
        coef
    );
    Out.ar(out, Pan2.ar(signal * envelope, pan));
}).add;
