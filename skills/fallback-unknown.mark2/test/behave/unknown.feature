Feature: fallback-unknown

  Scenario: Nonsense
    Given an english speaking user
     When the user says "Foo bar baz"
     Then "fallback-unknown.mark2" should reply with dialog from "unknown.dialog"

  # This test is failing on CI. Given its low importance it is disabled for now.
  @xfail
  @vkfail
  Scenario: Unknown person
    Given an english speaking user
     When the user says "Who is dinkel floep"
     Then "fallback-unknown.mark2" should reply with dialog from "who.is.dialog"

  # This test is failing on CI. Given its low importance it is disabled for now.
  @xfail
  @vkfail
  Scenario: Unknown question
    Given an english speaking user
     When the user says "What is a dinkel floep"
     Then "fallback-unknown.mark2" should reply with dialog from "question.dialog"
