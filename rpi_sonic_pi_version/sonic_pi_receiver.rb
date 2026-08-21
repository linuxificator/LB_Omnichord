require "json"

# A shorter schedule-ahead window keeps the internally timed rhythm stable
# while reducing how long an already-scheduled old chord can remain audible.
set_sched_ahead_time! 0.1

# Chord and bass note state arrives atomically in one OSC message.
set :chord_notes, []
set :bass_notes, []

set :manual_chord_nodes, {}
set :manual_chord_releases, {}

set :rhythm_chord_nodes, []

set :chord_amp, 0.5
set :chord_synth, :prophet
set :chord_synth_params, {
  attack: 0.0,
  decay: 0.0,
  sustain: 0.0,
  release: 1.0,
  cutoff: 110.0,
  res: 0.7
}

set :strum_amp, 0.5
set :strum_synth, :pluck
set :strum_synth_params, {
  attack: 0.0,
  decay: 0.0,
  sustain: 0.0,
  release: 1.0,
  noise_amp: 0.8,
  pluck_decay: 30.0,
  coef: 0.3
}

set :bass_synth, :fm
set :bass_synth_params, {
  attack: 0.0,
  decay: 0.0,
  sustain: 0.0,
  release: 1.0,
  divisor: 2.0,
  depth: 1.0
}
set :bass_amp, 0.5
set :bass_running, 1

set :percussion_amp, 0.5
set :rhythm_running, 0
set :rhythm_config_json, ""
set :rhythm_chord_enabled, 0

# Phrase-position state for the bar-by-bar scheduler.
set :rhythm_pattern_id, ""
set :rhythm_bar_index, 0

define :panic_all_omnichord_audio do
  set :rhythm_running, 0
  set :rhythm_chord_enabled, 0
  set :bass_running, 0
  set :rhythm_pattern_id, ""
  set :rhythm_bar_index, 0

  # Stop sustained/manual voices and the currently tracked rhythm chord.
  # Short-lived strum/bass/percussion notes are intentionally not registered
  # in global time-state; after transport is stopped they finish naturally.
  stop_all_manual_chords
  stop_current_rhythm_chord
end

define :options_from_osc do |values|
  params = {}

  values.each_slice(2) do |name, value|
    params[name.to_sym] = value.to_f
  end

  params
end

define :manual_chord_nodes_map do
  value = get(:manual_chord_nodes)
  value.nil? ? {} : value.to_h
end

define :manual_chord_releases_map do
  value = get(:manual_chord_releases)
  value.nil? ? {} : value.to_h
end

define :stop_manual_chord do |voice_id|
  key = voice_id.to_s.to_sym
  node_map = manual_chord_nodes_map
  release_map = manual_chord_releases_map

  nodes = node_map[key] || []
  release_time =
    (release_map[key] || 0.15).to_f
  release_time = 0.02 if release_time < 0.02

  nodes.each do |node|
    begin
      control node,
        amp_slide: release_time,
        amp: 0
    rescue StandardError
      # A short percussive voice may already have ended.
    end
  end

  node_map.delete(key)
  release_map.delete(key)
  set :manual_chord_nodes, node_map
  set :manual_chord_releases, release_map

  unless nodes.empty?
    in_thread do
      sleep release_time + 0.02

      nodes.each do |node|
        begin
          stop_synth_id(node)
        rescue StandardError
        end
      end
    end
  end
end

define :retune_nodes do |nodes, notes|
  success =
    !nodes.empty? &&
    nodes.length == notes.length

  if success
    nodes.each_with_index do |node, index|
      begin
        control node,
          note_slide: 0.02,
          note: notes[index]
      rescue StandardError
        success = false
      end
    end
  end

  success
end

define :update_manual_chord do |voice_id, notes|
  key = voice_id.to_s.to_sym
  node_map = manual_chord_nodes_map
  nodes = node_map[key] || []

  unless retune_nodes(nodes, notes)
    # The finger is still held, so replacing this one voice is safe if its
    # synth cannot be controlled or chord size has changed.
    unless nodes.empty?
      stop_manual_chord key
      start_manual_chord key, notes
    end
  end
end

define :stop_all_manual_chords do
  node_map = manual_chord_nodes_map
  keys = node_map.keys

  keys.each do |key|
    stop_manual_chord key
  end

  set :manual_chord_nodes, {}
  set :manual_chord_releases, {}
end

define :start_manual_chord do |voice_id, notes|
  key = voice_id.to_s.to_sym

  # Retriggering one button only replaces that button's own voice.
  stop_manual_chord key

  unless notes.empty?
    use_synth get(:chord_synth)

    opts = get(:chord_synth_params).to_h
    opts[:amp] = get(:chord_amp)

    release_time =
      opts.fetch(:release, 0.15).to_f

    opts[:sustain] = 3600.0
    opts[:amp_slide] = 0.0

    nodes = notes.map do |note|
      play note, **opts
    end

    node_map = manual_chord_nodes_map
    release_map = manual_chord_releases_map

    node_map[key] = nodes
    release_map[key] = release_time

    set :manual_chord_nodes, node_map
    set :manual_chord_releases, release_map
  end
end

define :play_chord_notes do |notes, event_amp = 1.0|
  unless notes.empty?
    use_synth get(:chord_synth)

    opts = get(:chord_synth_params).to_h
    opts[:amp] = get(:chord_amp) * event_amp

    play_chord notes, **opts
  end
end

define :play_current_chord_once do |event_amp = 1.0|
  notes = get(:chord_notes)

  unless notes.empty?
    use_synth get(:chord_synth)

    opts = get(:chord_synth_params).to_h
    opts[:amp] = get(:chord_amp) * event_amp

    nodes = notes.map do |note|
      play note, **opts
    end

    set :rhythm_chord_nodes, nodes
  end
end

define :stop_current_rhythm_chord do
  nodes = get(:rhythm_chord_nodes) || []

  nodes.each do |node|
    begin
      control node,
        amp_slide: 0.03,
        amp: 0
    rescue StandardError
    end
  end

  set :rhythm_chord_nodes, []
end

define :retune_current_rhythm_chord do |notes|
  nodes = get(:rhythm_chord_nodes) || []

  # Do not create a new note event from an octave/inversion button.
  unless nodes.empty?
    if notes.empty?
      nodes.each do |node|
        begin
          control node,
            amp_slide: 0.04,
            amp: 0
        rescue StandardError
        end
      end

      set :rhythm_chord_nodes, []
    else
      success = retune_nodes(nodes, notes)

      # A dead previous rhythm chord is forgotten, not restarted.
      set :rhythm_chord_nodes, [] unless success
    end
  end
end

define :play_current_bass_once do |degree, event_amp = 1.0|
  notes = get(:bass_notes)

  if get(:bass_running) == 1 && !notes.empty?
    note = notes[degree.to_i % notes.length]

    use_synth get(:bass_synth)

    opts = get(:bass_synth_params).to_h
    opts[:amp] = get(:bass_amp) * event_amp

    play note, **opts
  end
end

live_loop :receive_chord_state do
  use_real_time

  json = sync("/osc*/chord/state")[0].to_s

  begin
    state = JSON.parse(
      json,
      symbolize_names: true
    )
  rescue StandardError => error
    puts "Chord-state JSON error: #{error}"
    next
  end

  chord_notes =
    (state[:notes] || []).map(&:to_f)
  bass_notes =
    (state[:bass_notes] || []).map(&:to_f)

  set :chord_notes, chord_notes
  set :bass_notes, bass_notes

  if state.key?(:rhythm_running) &&
     !state[:rhythm_running]
    # Treat the GUI chord packet as authoritative. This closes a startup race
    # where a stale rhythm_player could still think transport was on until
    # the separate /rhythm/running receiver processed its packet.
    set :rhythm_running, 0
    set :rhythm_chord_enabled, 0
    set :rhythm_pattern_id, ""
    set :rhythm_bar_index, 0
    stop_current_rhythm_chord
  end

  # The exact notes to play and the state update came in the same OSC packet,
  # so there is no note/trigger ordering race.
  if state[:play_now]
    play_chord_notes chord_notes
  elsif (
    get(:rhythm_running) == 1 &&
    get(:rhythm_chord_enabled) == 1
  )
    retune_current_rhythm_chord chord_notes
  end
end

live_loop :receive_chord_manual do
  use_real_time

  json =
    sync("/osc*/chord/manual")[0].to_s

  begin
    event = JSON.parse(
      json,
      symbolize_names: true
    )
  rescue StandardError => error
    puts "Manual-chord JSON error: #{error}"
    next
  end

  action = event[:action].to_s
  voice_id = event[:id].to_s

  case action
  when "start"
    if event.key?(:rhythm_running) &&
       !event[:rhythm_running]
      set :rhythm_running, 0
      set :rhythm_chord_enabled, 0
      set :rhythm_pattern_id, ""
      set :rhythm_bar_index, 0
      stop_current_rhythm_chord
    end

    notes =
      (event[:notes] || []).map(&:to_f)

    start_manual_chord voice_id, notes

  when "update"
    notes =
      (event[:notes] || []).map(&:to_f)

    update_manual_chord voice_id, notes

  when "stop"
    stop_manual_chord voice_id

  when "stop_all"
    stop_all_manual_chords
  end
end

live_loop :receive_chord_amp do
  use_real_time

  set :chord_amp,
      sync("/osc*/chord/amp")[0].to_f
end

live_loop :receive_chord_synth do
  use_real_time

  set :chord_synth,
      sync("/osc*/chord/synth/name")[0].to_sym
end

live_loop :receive_chord_synth_params do
  use_real_time

  set :chord_synth_params,
      options_from_osc(
        sync("/osc*/chord/synth/params")
      )
end

live_loop :receive_strum_amp do
  use_real_time

  set :strum_amp,
      sync("/osc*/strum/amp")[0].to_f
end

live_loop :receive_strum_synth do
  use_real_time

  set :strum_synth,
      sync("/osc*/strum/synth/name")[0].to_sym
end

live_loop :receive_strum_synth_params do
  use_real_time

  set :strum_synth_params,
      options_from_osc(
        sync("/osc*/strum/synth/params")
      )
end

live_loop :receive_bass_amp do
  use_real_time

  set :bass_amp,
      sync("/osc*/bass/amp")[0].to_f
end

live_loop :receive_bass_running do
  use_real_time

  set :bass_running,
      sync("/osc*/bass/running")[0].to_i
end

live_loop :receive_bass_synth do
  use_real_time

  set :bass_synth,
      sync("/osc*/bass/synth/name")[0].to_sym
end

live_loop :receive_bass_synth_params do
  use_real_time

  set :bass_synth_params,
      options_from_osc(
        sync("/osc*/bass/synth/params")
      )
end

live_loop :receive_strum_note do
  use_real_time

  note = sync("/osc*/strum/note")[0].to_f

  use_synth get(:strum_synth)

  opts = get(:strum_synth_params).to_h
  opts[:amp] = get(:strum_amp)

  play note, **opts
end

live_loop :receive_percussion_amp do
  use_real_time

  set :percussion_amp,
      sync("/osc*/rhythm/amp")[0].to_f
end

live_loop :receive_panic do
  use_real_time

  sync("/osc*/panic")
  panic_all_omnichord_audio
end

live_loop :receive_rhythm_running do
  use_real_time

  new_state =
    sync("/osc*/rhythm/running")[0].to_i

  # Starting after a stop begins at the first bar of the phrase.
  if new_state == 1 && get(:rhythm_running) != 1
    set :rhythm_pattern_id, ""
    set :rhythm_bar_index, 0
  end

  if new_state != 1
    # No automatic chord can survive transport OFF.
    set :rhythm_chord_enabled, 0
    stop_current_rhythm_chord
  end

  set :rhythm_running, new_state

  # Important: this is intentionally the same wake behaviour as the
  # previously measured low-CPU receiver. Even an OFF message wakes the
  # player once; it then observes OFF, blocks on sync again, and remains idle.
  cue :omnichord_rhythm_wake
end

live_loop :receive_rhythm_config do
  use_real_time

  set :rhythm_config_json,
      sync("/osc*/rhythm/config")[0].to_s

  # This initial/config wake is part of the receiver version which previously
  # reduced idle Sonic Pi CPU to roughly 1.5% on the Raspberry Pi 5.
  cue :omnichord_rhythm_wake
end

live_loop :receive_rhythm_chord_enabled do
  use_real_time

  set :rhythm_chord_enabled,
      sync("/osc*/rhythm/chord/enabled")[0].to_i
end

# Percussion, bass and chord events still share one Sonic Pi timeline, but
# the stored configuration is now re-read once per bar rather than once per
# complete phrase. Most patterns in rhythms.json are two-bar phrases, so an
# activity or tempo change now takes effect at the next bar boundary.
live_loop :rhythm_player do
  json = get(:rhythm_config_json)

  if (
    get(:rhythm_running) != 1 ||
    json.nil? ||
    json.empty?
  )
    # Old code polled every 50 ms here, waking Ruby 20 times per second even
    # when the instrument was completely idle. Block on a local event instead.
    #
    # receive_rhythm_running and receive_rhythm_config cue this event after
    # updating their state. Once transport is OFF, this sync remains blocked.
    sync :omnichord_rhythm_wake
    next
  end

  begin
    config = JSON.parse(
      json,
      symbolize_names: true
    )
  rescue StandardError => error
    puts "Rhythm JSON error: #{error}"
    sleep 0.25
    next
  end

  use_bpm config[:tempo].to_f

  # Convert the written metre to Sonic Pi beat units:
  #
  #   4/4 -> 4 beats per bar
  #   3/4 -> 3 beats per bar
  #   6/8 -> 3 beats per bar
  #   7/8 -> 3.5 beats per bar
  #
  # All current rhythm definitions contain an integral number of bars.
  meter_parts =
    config[:meter].to_s.split("/").map(&:to_f)

  if (
    meter_parts.length == 2 &&
    meter_parts[1] > 0
  )
    bar_beats =
      meter_parts[0] * 4.0 / meter_parts[1]
  else
    bar_beats = config[:length_beats].to_f
  end

  phrase_beats = config[:length_beats].to_f

  bar_count = [
    (phrase_beats / bar_beats).round,
    1
  ].max

  pattern_id = config[:id].to_s
  previous_pattern_id =
    get(:rhythm_pattern_id).to_s

  bar_index = get(:rhythm_bar_index).to_i

  # Selecting another rhythm starts its phrase at bar one. Changing tempo or
  # activity within the same rhythm keeps the current phrase position.
  if pattern_id != previous_pattern_id
    bar_index = 0
    set :rhythm_pattern_id, pattern_id
  end

  bar_index %= bar_count

  bar_start = bar_index * bar_beats
  bar_end = bar_start + bar_beats
  epsilon = 0.000001

  timeline = []

  config[:percussion_events].each do |event|
    event_time = event[:time].to_f

    if (
      event_time >= bar_start - epsilon &&
      event_time < bar_end - epsilon
    )
      timeline << [
        event_time - bar_start,
        :percussion,
        event
      ]
    end
  end

  config[:bass_events].each do |event|
    event_time = event[:time].to_f

    if (
      event_time >= bar_start - epsilon &&
      event_time < bar_end - epsilon
    )
      timeline << [
        event_time - bar_start,
        :bass,
        event
      ]
    end
  end

  config[:chord_events].each do |event|
    event_time = event[:time].to_f

    if (
      event_time >= bar_start - epsilon &&
      event_time < bar_end - epsilon
    )
      timeline << [
        event_time - bar_start,
        :chord,
        event
      ]
    end
  end

  priority = {
    percussion: 0,
    bass: 1,
    chord: 2
  }

  timeline.sort_by! do |time, kind, event|
    [time, priority[kind]]
  end

  previous_time = 0.0
  aborted = false

  timeline.each do |time, kind, event|
    if get(:rhythm_running) != 1
      aborted = true
      break
    end

    wait = time - previous_time
    sleep wait if wait > 0
    previous_time = time

    # Transport may have been switched off while this loop was sleeping for
    # the next scheduled event. Check again immediately before sounding it.
    if get(:rhythm_running) != 1
      aborted = true
      break
    end

    case kind
    when :percussion
      options = {
        amp: event[:amp].to_f *
             get(:percussion_amp),
        rate: event.fetch(:rate, 1.0).to_f,
        pan: event.fetch(:pan, 0.0).to_f
      }

      sample event[:sample].to_sym, **options

    when :bass
      play_current_bass_once(
        event.fetch(:degree, 0).to_i,
        event.fetch(:amp, 1.0).to_f
      )

    when :chord
      if get(:rhythm_chord_enabled) == 1
        play_current_chord_once(
          event.fetch(:amp, 1.0).to_f
        )
      end
    end
  end

  if aborted
    # A transport-OFF/preset change can abort this live_loop iteration before
    # it reaches any scheduled sleep. Sonic Pi requires every live_loop
    # iteration to sleep or sync at least once.
    #
    # Do not use a tiny synthetic sleep here. Transport is OFF, so the correct
    # state is simply to block until a later rhythm/config state change wakes
    # us. This satisfies Sonic Pi's live_loop rule without polling or creating
    # any extra scheduler activity.
    sync :omnichord_rhythm_wake
    next
  end

  remainder = bar_beats - previous_time
  sleep remainder if remainder > 0

  set :rhythm_bar_index,
      (bar_index + 1) % bar_count
end
