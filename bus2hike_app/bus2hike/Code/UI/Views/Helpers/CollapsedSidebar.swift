//
//  CollapsedSidebar.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import SwiftUI

struct CollapsedSidebar: View {
   
   @Binding var showSidebar: Bool
   
   var body: some View {
      ZStack {
         VStack {
            Image(systemName: "line.3.horizontal")
               .bold()
               .foregroundStyle(.blue)
               .onTapGesture {
                  withAnimation {
                     showSidebar.toggle()
                  }
               }
            Spacer()
         }
         .padding()
         .frame(width: 50)
         .background(.ultraThinMaterial)
      }
      .shadow(color: .black.opacity(0.18), radius: 16, x: 8, y: 0)
   }
}
