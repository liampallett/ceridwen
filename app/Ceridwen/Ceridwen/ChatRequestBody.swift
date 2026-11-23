//
//  ChatRequestBody.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import Foundation

struct ChatRequestBody: Encodable {
    let model: String
    let message: String
    let threadId: String
}
