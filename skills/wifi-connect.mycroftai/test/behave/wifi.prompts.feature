Feature: wifi-setup-prompts

  Scenario: Start Wifi Setup
    Given an english speaking user
     When no network is detected
     Then "wifi-connect" should reply with dialog from "network-connection-needed.dialog"
