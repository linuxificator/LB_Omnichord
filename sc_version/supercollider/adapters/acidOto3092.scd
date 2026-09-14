/* Preserve upstream acidOto3092 while bounding its filter over the UI register. */
SynthDef("acidOto3092", {
    |out=0, freq=440, amp=0.1, pan=0, att=0.001, rel=0.5,
     lagTime=0.12, filterRange=6, width=0.51, rq=0.3|
    var pitch = freq.cpsmidi;
    var ampEnv = Env.perc(att, rel, amp).kr(doneAction: Done.freeSelf);
    var filterEnv = Env.perc(att, rel, filterRange * 12).kr;
    var cutoff = (pitch + filterEnv).midicps.clip(20, SampleRate.ir * 0.45);
    var signal = LFPulse.ar(pitch.midicps, width: width).range(-1, 1);

    signal = RLPF.ar(signal, cutoff, rq).distort * ampEnv;
    Out.ar(out, Pan2.ar(signal, pan));
}).add;
