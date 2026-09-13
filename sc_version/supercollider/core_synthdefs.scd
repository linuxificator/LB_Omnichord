/* Owned engine voices, bus strips and room effect. Safe to compile headless. */
(
SynthDef(\omniVoice, {
    |out=0, freq=440, velocity=0.7, gate=1, gain=1, pan=0,
     bendBus=0, attack=0.008, release=0.22, brightness=0.55|
    var bend = In.kr(bendBus, 1).max(0.01);
    var pitched = freq.max(10) * bend;
    var envelope = EnvGen.kr(
        Env.adsr(attack.max(0.001), 0.12, 0.72, release.max(0.005)),
        gate,
        doneAction: Done.freeSelf
    );
    var cutoff = (pitched * (3 + (brightness.clip(0, 1) * 10)))
        .clip(80, SampleRate.ir * 0.45);
    var source = VarSaw.ar(pitched, 0, 0.42, 0.42)
        + Pulse.ar(pitched * 0.5, 0.48, 0.20)
        + SinOsc.ar(pitched, 0, 0.12);
    var signal = RLPF.ar(source, cutoff, 0.55);
    Out.ar(out, Pan2.ar(
        signal * envelope * velocity.clip(0, 1) * gain,
        pan
    ));
}).add;

SynthDef(\omniDrum, { |out=0, note=36, velocity=0.7, gain=1|
    var isKick = note < 41;
    var isHat = note > 49;
    var noiseCutoff = Select.kr(isHat, [900, 5000]);
    var noiseDecay = Select.kr(isHat, [0.20, 0.09]);
    var outputDecay = Select.kr(isKick, [0.24, 0.34]);
    var bodyFreq = note.midicps.clip(45, 420);
    var body = SinOsc.ar(
        XLine.kr(bodyFreq * 2.2, bodyFreq, 0.06),
        0,
        EnvGen.kr(Env.perc(0.001, 0.28), doneAction: 0)
    );
    var noise = HPF.ar(WhiteNoise.ar, noiseCutoff)
        * EnvGen.kr(Env.perc(0.001, noiseDecay), doneAction: 0);
    var envelope = EnvGen.kr(
        Env.perc(0.001, outputDecay),
        doneAction: Done.freeSelf
    );
    var signal = Select.ar(isHat, [body + (noise * 0.35), noise]);
    Out.ar(out, (signal * envelope * velocity.clip(0, 1) * gain) ! 2);
}).add;

SynthDef(\omniVoiceOutput, {
    |in=0, out=0, velocity=0.7, gain=1, pan=0, gate=1, release=0.22|
    var input = In.ar(in, 2);
    var envelope = EnvGen.kr(
        Env.asr(0.003, 1, release.max(0.005)),
        gate,
        doneAction: Done.freeSelf
    );
    var signal = Balance2.ar(input[0], input[1], pan);
    Out.ar(out, signal * envelope * velocity.clip(0, 1) * gain);
}).add;

SynthDef(\omniBusStrip, {
    |in=0, out=0, roomOut=0, gain=1, roomSend=1|
    var signal = In.ar(in, 2);
    Out.ar(out, signal * gain);
    Out.ar(roomOut, signal * roomSend);
}).add;

SynthDef(\omniRoom, {
    |in=0, out=0, level=0, room=0.5, damping=0.5, master=1|
    var signal = In.ar(in, 2);
    var wet = FreeVerb2.ar(
        signal[0], signal[1], 1,
        room.clip(0, 1), damping.clip(0, 1)
    );
    Out.ar(out, wet * level.max(0) * master.clip(0, 1));
}).add;
)
