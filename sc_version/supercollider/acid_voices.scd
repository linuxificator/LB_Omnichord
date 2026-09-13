/* Native acid voices sharing one explicit gesture-control contract. */
(
~omniBuildAcidVoice = { |name, model|
    SynthDef(name, {
        |out=0, freqTargetHz=110, gate=1, velocity=0.7, gain=1,
         waveform=0, cutoffHz=400, resonanceNormalized=0.35,
         envOctaves=2, filterDecaySeconds=0.25,
         slideSeconds=0.060, slideEnabled=0,
         t_attack=1, t_filter=1, t_accent=0, accentAmount=0.35,
         pitchBendBus=0, release=0.18|
        var bend = In.kr(pitchBendBus, 1).max(0.01);
        var targetMidi = freqTargetHz.max(10).cpsmidi;
        var glidingMidi = VarLag.kr(targetMidi, slideSeconds.max(0.001));
        var pitchMidi = Select.kr(slideEnabled.clip(0, 1), [
            targetMidi,
            glidingMidi
        ]);
        var frequency = pitchMidi.midicps * bend;
        var filterEnvelope = Decay2.kr(
            Trig1.kr(t_filter, ControlDur.ir),
            0.003,
            filterDecaySeconds.max(0.01)
        );
        var accentEnvelope = Decay2.kr(
            Trig1.kr(t_accent, ControlDur.ir),
            0.001,
            (filterDecaySeconds * 0.55).max(0.01)
        );
        var attackTransient = Decay2.kr(
            Trig1.kr(t_attack, ControlDur.ir), 0.001, 0.025
        );
        var amplitude = EnvGen.kr(
            Env.asr(0.006, 1, release.max(0.01)),
            gate,
            doneAction: Done.freeSelf
        );
        var filterFrequency = (
            cutoffHz.max(20)
            * (2 ** (envOctaves.max(0) * filterEnvelope))
            * (2 ** (2 * accentAmount.clip(0, 1) * accentEnvelope))
        ).clip(20, SampleRate.ir * 0.45);
        var saw = Saw.ar(frequency);
        var pulse = Pulse.ar(frequency, 0.5);
        var source;
        var filtered;
        if(model == 0) {
            source = SelectX.ar(waveform.clip(0, 1), [saw, pulse]).tanh;
        };
        if(model == 1) {
            source = (pulse + (VarSaw.ar(frequency * 1.003, 0, 0.35) * 0.4)).tanh;
        };
        if(model == 2) {
            source = Mix.ar([
                saw,
                Pulse.ar(frequency * 0.5, 0.48) * 0.55,
                Saw.ar(frequency * 1.006) * 0.35
            ]) * 0.55;
        };
        if(model == 3) {
            source = Mix.ar(VarSaw.ar(
                frequency * [0.995, 1.0, 1.007],
                0,
                [0.38, 0.5, 0.62]
            )) * 0.34;
            source = (source * 1.8).tanh;
        };
        if(model == 2) {
            filtered = MoogFF.ar(
                source,
                filterFrequency,
                resonanceNormalized.clip(0, 1) * 3.8
            );
        } {
            filtered = RLPF.ar(
                source,
                filterFrequency,
                resonanceNormalized.linexp(0, 1, 0.9, 0.08)
            );
        };
        filtered = LeakDC.ar((filtered * (1.2 + (model * 0.18))).tanh);
        Out.ar(
            out,
            (filtered * amplitude * velocity.clip(0, 1) * gain
                * (1 + (0.08 * attackTransient))
                * (1 + (0.5 * accentAmount.clip(0, 1) * accentEnvelope))) ! 2
        );
    }).add;
};

~omniBuildAcidVoice.value(\omniAcid303, 0);
~omniBuildAcidVoice.value(\omniAcidOto, 1);
~omniBuildAcidVoice.value(\omniAcidMoog, 2);
~omniBuildAcidVoice.value(\omniAcidWarsaw, 3);

~omniAcidProgramName = { |program|
    switch(program.asString,
        "sc.omni.acid303", { \omniAcid303 },
        "sc.omni.acidOto", { \omniAcidOto },
        "sc.omni.acidMoog", { \omniAcidMoog },
        "sc.omni.acidWarsaw", { \omniAcidWarsaw },
        { nil }
    )
};

~omniAcidArgs = { |program, revision|
    var args = List.new;
    ~omniPreparedArgs.value(program, revision).pairsDo { |name, rawValue|
        var target = switch(name.asString,
            "filter_hz", { \cutoffHz },
            "resonance", { \resonanceNormalized },
            "filter_env_octaves", { \envOctaves },
            "filter_decay_ms", { \filterDecaySeconds },
            "portamento_ms", { \slideSeconds },
            "accent_amount", { \accentAmount },
            { name.asSymbol }
        );
        var value = rawValue;
        if(["filter_decay_ms", "portamento_ms"].includesEqual(name.asString)) {
            value = rawValue / 1000;
        };
        if(name.asString == "resonance") {
            value = rawValue.linlin(0.51, 12, 0, 1).clip(0, 1);
        };
        if(["articulation", "accent"].includesEqual(name.asString).not) {
            args.add(target); args.add(value);
        };
    };
    args.asArray
};
)
