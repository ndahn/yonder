# Simple Sounds

```mermaid
flowchart TD
    Play["[Event]" Play_x123456789] -->|Play-Action| RSC(RandomSequenceContainer)
    Stop["[Event]" Stop_x123456789] -->|Stop-Action| RSC
    RSC --> S1(Sound1)
    RSC --> S2(Sound2)
    RSC --> SN(...)
```

Creates a simple one-shot sound structure. Based on the selected playback mode, sounds added will be either played back in sequence or at random. See [RandomSequenceContainers](../wwise/containers.md#random-sequence-container) for more details.
