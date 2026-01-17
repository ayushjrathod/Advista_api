/*
  Warnings:

  - The values [researching,completed] on the enum `ChatSessionStatus` will be removed. If these variants are still used in the database, this will fail.

*/
-- AlterEnum
BEGIN;
CREATE TYPE "ChatSessionStatus_new" AS ENUM ('initialized', 'brief_generated');
ALTER TABLE "chat_sessions" ALTER COLUMN "status" DROP DEFAULT;
ALTER TABLE "chat_sessions" ALTER COLUMN "status" TYPE "ChatSessionStatus_new" USING ("status"::text::"ChatSessionStatus_new");
ALTER TYPE "ChatSessionStatus" RENAME TO "ChatSessionStatus_old";
ALTER TYPE "ChatSessionStatus_new" RENAME TO "ChatSessionStatus";
DROP TYPE "ChatSessionStatus_old";
ALTER TABLE "chat_sessions" ALTER COLUMN "status" SET DEFAULT 'initialized';
COMMIT;
