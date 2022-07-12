Feature: Manage the device wallpaper

  Scenario Outline: Allow user to change the device wallpaper
    Given an english speaking user
      When the user says "<wallpaper change request>"
      Then the wallpaper should be changed

   Examples: change the wallpaper
     | wallpaper change request |
     | change the wallpaper |
     | change current wallpaper |
     | change homescreen wallpaper |
     | change background |

  Scenario Outline: Allow user to change to a named wallpaper
    Given an english speaking user
      When the user says "<wallpaper name request>"
      Then the wallpaper should be changed to "<name>"

   Examples: change the wallpaper
     | wallpaper name request | name |
     | change wallpaper to green | green |
     | change wallpaper to blue | blue |
     | change wallpaper to moon | moon |
