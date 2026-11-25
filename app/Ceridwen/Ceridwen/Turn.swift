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
    let id: UUID
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
            let turn = Turn(id: message.id, prompt: message.content)
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
        case "tool":
            // Give this result to the first tool step of the same name that's
            // still waiting for one. Results arrive in the order the calls were
            // made, so two calls to the same tool still get the right results.
            let last = turns.count - 1
            let waiting = turns[last].steps.firstIndex { step in
                if case .tool(let name, .none) = step { return name == message.toolName }
                return false
            }
            if let index = waiting {
                turns[last].steps[index] = .tool(name: message.toolName ?? "", result: message.content)
            }
        default:
            break
        }
    }
    
    return turns
}
