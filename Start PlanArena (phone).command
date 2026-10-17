#!/bin/zsh
# Starts PlanArena so a phone on the same Wi-Fi can open the game.
cd "$(dirname "$0")"
exec "./Start PlanArena.command" --phone
