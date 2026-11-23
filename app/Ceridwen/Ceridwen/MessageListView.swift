//
//  MessageListView.swift
//  Ceridwen
//
//  Created by Liam Pallett on 2026-11-23.
//

import Foundation
import SwiftUI
import Textual

struct MessageListView: View {
    let messages: [Message]
    
    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 12) {
                let filtered = messages.filter {
                    message in message.role != "tool" && !message.content.isEmpty
                }
                ForEach(filtered) { message in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(message.role.capitalized)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        StructuredText(markdown: message.content)
                            .textSelection(.enabled)
                    }
                }
            }
            .padding()
        }
        .defaultScrollAnchor(.bottom)
    }
}
