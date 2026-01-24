-- CreateEnum
CREATE TYPE "ResearchSessionStatus" AS ENUM ('pending', 'researching', 'processing', 'synthesizing', 'completed', 'failed');

-- AlterTable
ALTER TABLE "chat_sessions" ADD COLUMN     "meta" JSONB;

-- CreateTable
CREATE TABLE "research_sessions" (
    "id" TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    "userId" TEXT,
    "researchBrief" JSONB,
    "status" "ResearchSessionStatus" NOT NULL DEFAULT 'pending',
    "taskIds" JSONB,
    "searchResults" JSONB,
    "processedResults" JSONB,
    "report" JSONB,
    "meta" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "research_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "research_sessions_threadId_key" ON "research_sessions"("threadId");

-- AddForeignKey
ALTER TABLE "research_sessions" ADD CONSTRAINT "research_sessions_threadId_fkey" FOREIGN KEY ("threadId") REFERENCES "chat_sessions"("threadId") ON DELETE CASCADE ON UPDATE CASCADE;
