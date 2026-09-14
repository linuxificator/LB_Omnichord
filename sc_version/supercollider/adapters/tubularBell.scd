/* Preserve upstream tubularBell while bounding its low-pass filter frequency. */
SynthDef(\tubularBell, {
    |freq=440, amp=0.1, pan=0, out=0, att=0.005, rel=9, exciterRel=0.05|
    var envelope = Env.perc(att, exciterRel, 0.05).kr;
    var signal = DynKlank.ar(
        Ref([
            [1.013, 1.512, 2.113, 2.525, 3.35, 4.57, 6.48],
            [1, 0.78, 0.89, 0.63, 0.31, 0.56, 0.25],
            [1, 0.9, 0.8, 0.65, 0.45, 0.3, 0.1]
        ]),
        GrayNoise.ar(envelope),
        freq,
        rel
    );

    signal = LPF.ar(signal, (freq * 9.5).clip(20, SampleRate.ir * 0.45));
    DetectSilence.ar(signal, 0.001, 0.5, doneAction: Done.freeSelf);
    Out.ar(out, Pan2.ar(signal, pan, amp));
}).add;
