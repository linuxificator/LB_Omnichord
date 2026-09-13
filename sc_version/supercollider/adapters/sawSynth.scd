/* LB routing adapter for the pinned SCLOrkSynths definition. */
SynthDef("sawSynth", {
    |out=0, freq=440, amp=0.1, att=0.1, rel=2,
     lofreq=1000, hifreq=3000, pan=0|
    var envelope = Env.perc(att, rel, amp).kr(doneAction: 2);
    var signal = Saw.ar(freq * [0.99, 1, 1.001, 1.008], envelope);
    signal = Mix.ar(LPF.ar(signal, LFNoise2.kr(1).range(lofreq, hifreq)));
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
