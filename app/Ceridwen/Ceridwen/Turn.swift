//
//  Turn.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-24.
//

import Foundation

enum Step {
    case thinking(String)
    case tool(name: String, result: String?)
}

struct Turn: Identifiable {
    let id = UUID()
    var prompt: String = ""
    var steps: [Step] = []
    var reply: String = ""
}

func groupIntoTurns(_ messages: [Message]) -> [Turn] {
    var turns: [Turn] = []
    
    for message in messages {
        if turns.isEmpty && message.role != "user" { continue }
        switch message.role {
        case "user":
            let turn = Turn(prompt: message.content)
            turns.append(turn)
        case "assistant":
            if !message.thinking.isEmpty {
                turns[turns.count - 1].steps.append(.thinking(message.thinking))
            }
            for call in message.toolCalls {
                turns[turns.count - 1].steps.append(.tool(name: call.name, result: nil))
            }
            if !message.content.isEmpty {
                turns[turns.count - 1].reply += message.content
            }
        default:
            break
        }
    }
    
    return turns
}
