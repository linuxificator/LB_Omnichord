/* Numeric-control serialization adapter for the pinned SCLOrk definition. */
SynthDef("kickBlocks", {
    |out=0, pan=2, amp=0.4, curve=(-4),
     t1freq=400, t1harmonic=2, t1glide=0.01,
     t1att=0.0005, t1rel=0.01, t1curve=(-4), t1del=0, t1amp=1,
     t2freq=50, t2harmonic=3.44, t2glide=0.01,
     t2att=0.0001, t2rel=0.3, t2curve=0, t2del=0.005, t2amp=1,
     h1freq=100, h1harmonic=8, h1glide=0.01, h1rq=0.6,
     h1att=0.001, h1rel=0.02, h1curve=(-4), h1del=0.001, h1amp=1,
     h2freq=1320, h2harmonic=1, h2glide=0,
     h2att=0.003, h2rel=0.03, h2curve=(-4), h2del=0, h2amp=0.5,
     cfreq=6100, crq=1, camp=1.41|
    var noise = Hasher.ar(Sweep.ar);
    var tone1 = SinOsc.ar(
        XLine.ar(t1freq * t1harmonic, t1freq, t1glide),
        mul: Env.perc(t1att, t1rel, t1amp, t1curve).delay(t1del).ar
    );
    var tone2 = SinOsc.ar(
        XLine.ar(t2freq * t2harmonic, t2freq, t2glide),
        mul: Env.perc(t2att, t2rel, t2amp, t2curve).delay(t2del).ar
    );
    var hit1 = BPF.ar(
        noise,
        XLine.ar(h1freq * h1harmonic, h1freq, h1glide),
        h1rq,
        Env.perc(h1att, h1rel, h1amp, h1curve).delay(h1del).ar
    );
    var hit2 = HPF.ar(
        noise,
        XLine.ar(h2freq * h2harmonic, h2freq, h2glide),
        Env.perc(h2att, h2rel, h2amp, h2curve).delay(h2del).ar
    );
    var click = BPF.ar(
        Impulse.ar(0) * SampleRate.ir / 48000,
        cfreq,
        crq,
        camp
    );
    var signal = Mix.ar(tone1 + tone2 + hit1 + hit2 + click).tanh * amp;

    DetectSilence.ar(signal, doneAction: 2);
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
