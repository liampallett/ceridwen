//
//  Message.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import Foundation

struct Message: Codable, Identifiable {
    let id = UUID()
    let role: String
    var content: String
    var thinking: String = ""
    let toolName: String?
    
    enum CodingKeys: String, CodingKey {
        case role
        case content
        case toolName
    }
}
