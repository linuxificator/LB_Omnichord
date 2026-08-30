cmake_minimum_required(VERSION 3.20)
project(lb_amy_service C)

if(NOT DEFINED AMY_ROOT)
    message(FATAL_ERROR "AMY_ROOT must point to the checked-out AMY fork")
endif()

file(TO_CMAKE_PATH "${AMY_ROOT}" AMY_ROOT_CMAKE)
set(AMY_SRC "${AMY_ROOT_CMAKE}/src")
set(AMY_SOURCES
    algorithms.c amy.c envelope.c examples.c parse.c filters.c
    oscillators.c pcm.c interp_partials.c custom.c delay.c log2_exp2.c
    patches.c transfer.c sequencer.c libminiaudio-audio.c instrument.c
    amy_midi.c api.c midi_mappings.c cv_trigger.c)
list(TRANSFORM AMY_SOURCES PREPEND "${AMY_SRC}/")

add_executable(amy_service amy_service.c ${AMY_SOURCES})
target_include_directories(amy_service PRIVATE "${AMY_SRC}")
target_compile_definitions(amy_service PRIVATE
    AMY_WAVETABLE _CRT_SECURE_NO_WARNINGS _USE_MATH_DEFINES)
target_compile_options(amy_service PRIVATE /O2 /W3 /std:c11 /experimental:c11atomics)
target_link_libraries(amy_service PRIVATE ws2_32 winmm ole32)
