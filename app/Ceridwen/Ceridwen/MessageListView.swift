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
                ForEach(groupIntoTurns(messages)) { turn in
                    VStack(alignment: .leading, spacing: 4) {
                        Text("User")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        StructuredText(markdown: turn.prompt)
                            .textual.textSelection(.enabled)

                        // hide the label until the model has produced something
                        if !turn.steps.isEmpty || !turn.reply.isEmpty {
                            Text("Assistant")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        if !turn.steps.isEmpty {
                            DisclosureGroup("Activity") {
                                VStack(alignment: .leading, spacing: 8) {
                                    ForEach(turn.steps.indices, id: \.self) { index in
                                        switch turn.steps[index] {
                                        case .thinking(let text):
                                            Text(text)
                                                .textSelection(.enabled)
                                                .frame(maxWidth: .infinity, alignment: .leading)
                                        case .tool(let name, let result):
                                            DisclosureGroup {
                                                Text(result ?? "Running…")
                                                    .font(.callout.monospaced())
                                                    .textSelection(.enabled)
                                                    .frame(maxWidth: .infinity, alignment: .leading)
                                            } label: {
                                                Label("Used \(name)", systemImage: "wrench.and.screwdriver")
                                            }
                                        }
                                    }
                                }
                            }
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .padding(.bottom, 8)
                        }

                        StructuredText(markdown: turn.reply)
                            .textual.textSelection(.enabled)
                    }
                }
            }
            .padding()
        }
        .defaultScrollAnchor(.bottom)
    }
}
