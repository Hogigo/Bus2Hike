//
//  DurationField.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import SwiftUI


struct DurationField: View {
    @Binding var duration: Duration

    var body: some View {
        VStack(alignment: .leading) {
            HStack {
               TextField("", value: $duration.hours, format: .number)
                    .frame(width: 40)
                    .textFieldStyle(.roundedBorder)

               Text("h")
                   .font(.caption)
               
                Text(":")

                TextField("", value: $duration.minutes, format: .number)
                    .frame(width: 40)
                    .textFieldStyle(.roundedBorder)
               
               Text("mins")
                   .font(.caption)
            }
        }
    }
}
