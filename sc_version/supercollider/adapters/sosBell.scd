/*
 * Serialization adapter for the pinned SCLOrkSynths definition.
 * SynthDef controls are numeric on the server; the upstream `curve = \lin`
 * default compiles in sclang but cannot be written or sent to scsynth.
 */
SynthDef("sosBell", {
    |freq=440, out=0, amp=0.1, pan=0, rel=2, curve=0,
     ringAmp=1, ringRel=0.9, wobbleDepth=0.6, wobbleMin=1, wobbleMax=1.8,
     strikeAmp=1, strikeDec=0.01, strikeRel=0.04, strikeDepth=0.028,
     strikeHarmonic=8, humAmp=0.5, humAtt=0.5, humDec=0.5, humRel=1|
    var ringFreqs = [2, 3, 4.1, 5.43, 6.8, 8.21];
    var ringEnv = Env.new(
        [1, 0.3, 0.2, 0],
        [1/3, 1/3, 1/3] * ringRel * rel,
        curve
    ).kr;
    var ring = SinOsc.ar(
        ringFreqs * freq,
        mul: Array.series(6, 1, -0.1) * ringEnv
    );
    var strikeEnv = Env.new(
        [1, 0.1, 0], [strikeDec, strikeRel * rel], curve
    ).kr;
    var strikeMod = LFNoise1.ar(freq * 36).range(
        1 / (strikeDepth + 1), strikeDepth + 1
    );
    var strike = SinOsc.ar(
        freq * strikeHarmonic * strikeMod,
        mul: strikeEnv
    );
    var humEnv = Env.new(
        [0, 1, 0.8, 0], [humAtt, humDec, humRel * rel], curve
    ).kr;
    var hum = SinOsc.ar(freq * [1.01, 0.47], mul: humEnv);
    var signal;

    ring = ring * LFTri.ar(
        { Rand(wobbleMin, wobbleMax) }.dup(6)
    ).range(1 - wobbleDepth, 1);
    signal = Mix.ar(
        (ring * ringAmp) + (strike * strikeAmp) + (hum * humAmp)
    ) * amp * 0.5;
    DetectSilence.ar(signal, doneAction: 2);
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
