//
//  ChatThread.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import Foundation

struct ChatThread: Codable, Identifiable {
    let id: String
    let title: String
    let createdAt: String
    let updatedAt: String
}
