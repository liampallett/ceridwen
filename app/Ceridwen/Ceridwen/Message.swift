//
//  Message.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import Foundation

struct Message: Decodable, Identifiable {
    let id = UUID()
    let role: String
    var content: String
    var thinking: String = ""
    let toolName: String?
    var toolCalls: [ToolCall] = []
    
    enum CodingKeys: String, CodingKey {
        case role
        case content
        case thinking
        case toolName
        case toolCalls
    }

    /// Ollama's saved shape for a tool call: `{"id": ..., "function": {"name": ...}}`.
    /// Only used to read history; `arguments` is ignored since nothing shows it yet.
    private struct StoredToolCall: Decodable {
        let id: String?
        let function: Function

        struct Function: Decodable {
            let name: String
        }
    }
}

extension Message {
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        role = try container.decode(String.self, forKey: .role)
        content = try container.decode(String.self, forKey: .content)
        thinking = try container.decodeIfPresent(String.self, forKey: .thinking) ?? ""
        toolName = try container.decodeIfPresent(String.self, forKey: .toolName)
        let stored = try container.decodeIfPresent([StoredToolCall].self, forKey: .toolCalls) ?? []
        toolCalls = stored.map { ToolCall(id: $0.id, name: $0.function.name) }
    }
}
