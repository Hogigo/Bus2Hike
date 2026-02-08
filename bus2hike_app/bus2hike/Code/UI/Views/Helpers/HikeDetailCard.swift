//
//  HikeDetailCard.swift
//  bus2hike
//
//  Created by Antonia Stieger on 01.02.26.
//

import SwiftUI

struct HikeDetailCard: View {
   let hike: Hike
   let onClose: () -> Void
   
   @State private var expanded = false
   
   var body: some View {
      VStack(spacing: 0) {
         Capsule()
            .frame(width: 40, height: 5)
            .foregroundStyle(.secondary)
            .padding(.top, 8)
         
         HStack(spacing: 12) {
            Image(hike.imageName)
               .resizable()
               .scaledToFill()
               .frame(width: 100, height: 80)
               .clipShape(RoundedRectangle(cornerRadius: 14))
            
            VStack(alignment: .leading, spacing: 6) {
               Text(hike.name)
                  .font(.headline)
                  .lineLimit(2)
               
               Text(hike.shortDescription)
                  .font(.subheadline)
                  .foregroundStyle(.secondary)
               
               HStack(spacing: 12) {
                   Label("\(hike.elevation_gain_m ?? 0)m", systemImage: "arrow.up")
                   Label("\(hike.elevation_loss_m ?? 0)m", systemImage: "arrow.down")
               }
               .font(.caption)
               .foregroundStyle(.secondary)
            }
            
            Spacer()
            
            Button {
               onClose()
            } label: {
               Image(systemName: "xmark.circle.fill")
                  .font(.title2)
                  .foregroundStyle(.blue)
            }
         }
         .padding()
         
         if expanded {
            Divider()
            
            ScrollView {
               Text(hike.longDescription)
                  .font(.body)
                  .padding()
            }
            .frame(maxHeight: 220)
            .transition(.move(edge: .bottom).combined(with: .opacity))
         }
         
      }
      .frame(width: 500)
      .background(.inverted)
      .clipShape(RoundedRectangle(cornerRadius: 22))
      .shadow(radius: 20)
      .padding(.horizontal)
      .onTapGesture {
         withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
            expanded.toggle()
         }
      }
   }
}
