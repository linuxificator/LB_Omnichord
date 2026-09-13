/* Numeric-control serialization adapter for the pinned SCLOrk definition. */
SynthDef("kik3", {
    |amp=1, out=0, pan=0, freq=66, att=0.01, dec=0.1,
     decaylevel=0.8, rel=0.3, envCurve=(-4), sweeptime=0.08,
     sweepCurve=(-4), harmonic=6, preamp=3|
    var envelope = Env.new(
        [0, amp, decaylevel * amp, 0],
        [att, dec, rel],
        envCurve
    ).kr(doneAction: 2);
    var frequencyEnvelope = Env.new(
        [freq * harmonic, freq], [sweeptime], sweepCurve
    ).kr;
    var signal = SinOsc.ar(frequencyEnvelope, mul: preamp).distort;

    signal = Normalizer.ar(signal, level: envelope);
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
