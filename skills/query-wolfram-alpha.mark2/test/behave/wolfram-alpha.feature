Feature: Wolfram Alpha Skill

  Scenario Outline: user asks a math question
    Given an english speaking user
     When the user says "<how do i math>"
     And "query-wolfram-alpha.mark2" reply should contain "<answer>"

  Examples: user asks a math question
    | how do i math | answer |
    | ask wolfram what is 10 times 10 | 100 |

  Scenario Outline: user asks a conversion question
    Given an english speaking user
     When the user says "<how many x in a y>"
     And "query-wolfram-alpha.mark2" reply should contain "<answer>"

  Examples: user asks a conversion question
    | how many x in a y | answer |
    | ask wolfram how many cups are in a gallon | 16 |
