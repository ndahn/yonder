I couldn't find any pattern other than that regions affecting sound start at 7500 and regions affecting rendering start at 8500. I don't think the region ID has any relation to the other parameters. as long as it's within the correct range. 

There are two params relevant to SoundRegions: `WwiseValueToStrParam_BgmBossChrIdConv` and `WwiseValueToStrParam_EnvPlaceType`. The former contains the boss bgm strings AND the BgmPlaceType strings (all starting with Bgm). The thing is, the SoundRegions refer to the EnvPlaceType param, where the strings tart with Env.

In Limgrave, the values for BgmPlaceType and EnvPlaceType default to `Bgm_000_Green` and `Env_000_Green`. I set my region env param to 100, which is Env_100_Castle. And then I changed the corresponding Bgm_100_Castle string in BgmBossChrIdConv (!) to something else. Lo and behold, when I enter the region the EnvPlaceType stays at Env_000_Green and the BgmPlaceType is updated! And I'm left scratching my brain =_=

There is seemingly no relation between the two params whatsoever. Their order is different, the row IDs are unrelated, and the string I put in didn't even have the same number in the middle anymore. Like.... wtf?