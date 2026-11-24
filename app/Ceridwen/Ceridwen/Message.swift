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
    }
}

extension Message {
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        role = try container.decode(String.self, forKey: .role)
        content = try container.decode(String.self, forKey: .content)
        thinking = try container.decodeIfPresent(String.self, forKey: .thinking) ?? ""
        toolName = try container.decodeIfPresent(String.self, forKey: .toolName)
    }
}
