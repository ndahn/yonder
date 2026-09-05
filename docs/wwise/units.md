# Units

## Volumes - dB (Decibel)

Human hearing follows a logarithmic curve, and so in order to double the perceived volume of a sound you actually need to increase the sound's power tenfold. The unit Bel (named after its inventor A. G. Bel) models this relation and is defined as ratio of two amplitudes:

$$
Q = 20 * \log\frac{P_1}{P_2} dB
$$

It's usually measured in tenths of a Bel which makes the units in most common scenarios more human-friendly. In Wwise, volume modifiers are added on top of the input signal's volume - i.e. if you add +6dB to the signal its amplitude will double (and at +10dB it will *sound* twice as loud).

## Frequencies - Hz (Hertz)

A pure tone like a an A-minor is a wave with a single frequency, and like water in a pond, many such waves can be overlayed on top of each other to form more complex patterns. This is what audio signals are, except that the waves now propagate through a 3-dimensional medium instead of across a surface - vibrations instead of waves, so to speak. The frequency of a wave is measured in Hertz, which describes how many peaks the wave has per second. Many filters and effects will have frequency settings to control what they are doing. For example, a band-pass filter would have two frequency limits and would try to suppress any frequencies outside of this range.

## Cents

Cents are a logarithmic unit for music intervals, i.e. an octave of 12 semitone of 100 cents each. This unit is often used when adjusting notes, and you may encounter it when adding a *pitch* property.

!!! info

    The pitch property adjusts the sound's pitch by altering its playback speed. To maintain speed you'd have to use a Harmonizer or Vocoder effect; however, doing a proper pitch shift without glitches is incredibly difficult and generally creates mediocre results past a certain range.

## Low-Pass & High-Pass Filters

In Wwise, the low-pass and high-pass filter *properties* don't use frequencies for their cutoff points. Instead they are using normalized units, i.e. percentage values that [map to a frequency table](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=associating_low_pass_filter_values_with_their_corresponding_cutoff_frequencies). This makes it easy to do addition and subtraction, which would not be possible with frequencies.

## Accumulation

All playback nodes in Wwise can have modifiers/properties, some of which may be controlled by [game parameters](game_parameters.md). As the tree-graph is traversed, these modifiers are accumulated and the final value is applied to the leave nodes/audio sources. This is true for volumes (dB), low-pass filters (Hz), and high-pass filters (Hz) (*and maybe pitch (Hz)*) - all other properties replace any previous values. Wwise has two [accumulation modes](https://www.audiokinetic.com/en/public-library/2025.1.10_9233/?source=Help&id=defining_filter_behavior): *addition* and *maximum*. Fromsoft is using __addition__.*
