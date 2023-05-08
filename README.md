

Instructions
==== 
Lifesmart devices for Home Assistant

Prerequisites: 
---
1. Find current LifeSmart region for your country (America, Europe, Asia Pacific, China (old, new , VIP))

1. New Application from LifeSmart Open Platform to obtain `app key` and `app token`, http://www.ilifesmart.com/open/login (caution! this url is not https and all content is in chinese, browse with translation should help)

1. Login to application created in previous bullet with LifeSmart user to grant 3rd party application access to get `user token`, please ensure you use the api address with correct region. 


How to install:
---
1. Copy the lifesmart directory to config/custom_components/

2. Add configuration in the configuration.yaml file:

```
lifesmart:
  appkey: "your_appkey" 
  apptoken: "your_apptoken"
  usertoken: "your_usertoken" 
  userid: "your_userid"
  exclude:
    - "0011" #The me value of the device needs to be shielded. This is temporarily required, and you can fill in any content
  exclude_agt:
    - "XXXX" #exlucde all devices in these smart stations
  ai_include_agt:
    - "XXXXXXXXX" # agt to be included for AI or Scene as a switch, fill any value to omit
  ai_include_me:
    - "xxxx" # me to be included for AI or Scene as a switch, fill any value to omit
 ```
 

Currently supported devices:
---
1. Switch;

2. Lighting: currently only supports Super Bowl night light;

3. Universal remote control;

4. Curtain motor (only support Duya motor)

5. Dynamic sensor, door sensor, environmental sensor, formaldehyde/gas sensor

6. Air conditioning control panel

7. Intelligent door lock information feedback

Update the description
---

### [Updated on October 2022, 9] by likso
1. Added scene_set service
2. Added ai and scene as a switch
3. Added included AI agt and me setting as a switch setting in configuration.yaml


### [Updated on July 2022, 12] by likso
1. Added async support
2. Fix entity_id format 
3. Added unique_id property
4. Added switch SL_NATURE, SL_SW_NS[1|2|3] support
5. Added light SL_SPOT colour and brightness support
6. Added light strip SL_CT_RGBW colour and brightness support
7. Added light SL_LI_WW colour temperature and brightness support
8. Fixed Door sensor SL_SC_BG open/closed status
9. Changed server url to https://api.us.ilifesmart.com/
10. Added excluded agt setting in configuration.yaml

Added the following into configuration.yaml：

### [Cumulative update on July 2022, 7]

Home Assitant new version adaptation:
- XXXDevice for XXXEntity
- FanSpeed enumeration modification
- device_state_attributes to extra_state_attributes
- In the Climate class, Uniform is modified to use built-in properties

### [Updated on December 2020, 12]

Support streamer switch light control

Update the manifest content to accommodate the new version of Home Assistant

### [Updated on December 2020, 8]

New device support:

Super panel: SL_NATURE

PS: It's actually a switch...

### [Updated on December 2020, 2]

Optimized entity ID generation logic: Solve the problem that there may be duplicates of the me number when there are no members or multiple smart centers.

### [Updated on December 2019, 12]

New supported devices:

Central air conditioning panel: V_AIR_P

Smart door lock feedback information: SL_LK_LS, SL_LK_GTM, SL_LK_AG, SL_LK_SG, SL_LK_YL

