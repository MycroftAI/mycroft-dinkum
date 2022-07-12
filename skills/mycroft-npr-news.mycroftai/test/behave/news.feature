Feature: mycroft-news

  Background:
    Given an english speaking user

  Scenario Outline: what's the news
    Given nothing is playing
    When the user says "<what's the news>"
    Then "mycroft-news" should reply with dialog from "news.dialog"

   Examples: What's the news - standard intent
     | what's the news |
     | news |
     | brief me |
     | other news |
     | what's new |
     | news briefing |
     | breaking news |
     | what's the news |
     | let's hear the news |
     | what's the latest news |
     | what's today's briefing |
     | what's the breaking news |
     | give me the news updates |
     | tell me what's happening |
     | brief me on the headlines |

  Scenario Outline: Play the news using Common Play Framework
    Given nothing is playing
    When the user says "<play the news>"
    Then "mycroft-playback-control" should reply with dialog from "news.dialog"

   Examples: play the news
     | play the news |
     | play the news |
     | play news |
     | play news briefing |
     | play headlines |
     | play the latest news |
     | play today's news |
     | play today's headlines |
     | play the news again |

  Scenario Outline: stop news playback
    Given news is playing
    When the user says "<stop the news>"
    Then "mycroft-news" should stop playing

   Examples: stop news playback
     | stop the news |
     | stop |
     | stop playing |

  @xfail
  # Jira MS-108 https://mycroft.atlassian.net/browse/MS-108
  Scenario Outline: Failing stop news playback
    Given news is playing
    When the user says "<stop the news>"
    Then "mycroft-news" should stop playing

   Examples: stop news playback
     | stop the news |
     | quit |
     | end |
     | turn it off |
     | turn off news |
     | turn off music |
     | shut it off |
     | shut up |
     | be quiet |
     | end playback |
     | silence |

  Scenario Outline: pause news playback
    When the user says "<pause the news>"
    Then "mycroft-news" should pause playing

   Examples: pause news playback
     | pause the news |
     | pause |

  Scenario Outline: play a specific news channel
    Given nothing is playing
    When the user says "<play a specific news channel>"
    Then mycroft reply should contain "<specified channel>"
    # Disabled until Mark II is better mocked.
    # Then "<specified channel>" should play

   Examples: play specific news channel
     | play a specific news channel | specified channel |
     | play the BBC news | BBC News |
     | Play the NPR news | NPR News Now |
     | Play AP hourly news | AP Hourly Radio News |
     | Play the news from Associated Press | AP Hourly Radio News |
     | Play CBC news | CBC News |
     | Play Fox News | Fox News |
     | Play PBS news | PBS NewsHour |
     | Play YLE news | YLE |
     | Play  DLF news | DLF |
     | Play WDR news | WDR |
     | play news from bbc | BBC News |
     | Play news from ekot | Ekot |
     | Play financial news | Financial Times |
     | Play news from the Financial Times | Financial Times |

  @xfail
  Scenario Outline: give me the news from channel
    When the user says "<give me news from a specific channel>"
    Then mycroft reply should contain "<specified channel>"

   Examples:
     | give me news from a specific channel | specified channel |
     | give me the news from bbc | BBC News |
     | give me the news from ekot | Ekot |
     | tell me the latest NPR news | NPR |
     | what are the latest headlines from Fox | Fox |
     | what are the headlines from WDR | WDR |

  Scenario Outline: play music with names similar to news channels
    When the user says "<play some music>"
    Then "NewsSkill" should not reply

    Examples:
      | play some music |
      | play metallica |
      | play 1live on tunein |
      | play sunshine on tunein |
      | play bigfm on tunein |
      | Play klassik lounge easy radio |
      | play the song monkey brains |
      | play the song skinamarinky dinky dink |
      | play the song python programming |
      | play the song covid-19 |

  Scenario Outline: play radio from stations not defined in News Skill
    When the user says "<play some radio station>"
    Then "NewsSkill" should not reply

    Examples:
      | play some radio station |
      | play kuow |
      | play kuow radio |

  Scenario Outline: Utterances unrelated to the News Skill
    When the user says "<something unrelated to this skill>"
    Then "NewsSkill" should not reply

    Examples:
      | something unrelated to this skill |
      | what time is it |
      | what's the weather |
      | cancel timer |