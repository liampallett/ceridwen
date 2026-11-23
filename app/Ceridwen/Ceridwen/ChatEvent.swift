//
//  ChatEvent.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import Foundation

struct ToolCall: Decodable{
    let id: String?
    let name: String
}

struct ToolResult: Decodable {
    let id: String?
    let name: String
    let result: String
    let success: Bool
}

enum ChatEvent: Decodable {
    case thinking(String)
    case content(String)
    case title(String)
    case error(String)
    case toolCall(ToolCall)
    case toolResult(ToolResult)
    case done
    case unknown
    
    enum CodingKeys: String, CodingKey {
        case type, data
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)
        
        switch type {
        case "thinking":
            self = .thinking(try container.decode(String.self, forKey: .data))
            
        case "content":
            self = .content(try container.decode(String.self, forKey: .data))
            
        case "title":
            self = .title(try container.decode(String.self, forKey: .data))
            
        case "error":
            self = .error(try container.decode(String.self, forKey: .data))
         
        case "tool_call":
            self = .toolCall(try container.decode(ToolCall.self, forKey: .data))
            
        case "tool_result":
            self = .toolResult(try container.decode(ToolResult.self, forKey: .data))
            
        case "done":
            self = .done
            
        default:
            self = .unknown
        }
    }
}
