// Adapted from the Astryx ai-chat page template (Meta Platforms, Inc. and affiliates).
import { HStack, VStack } from "@astryxdesign/core/Layout";
import { Button } from "@astryxdesign/core/Button";
import { Text } from "@astryxdesign/core/Text";
import { FileText, X } from "lucide-react";
import { formatFileSize, type Attachment } from "../chat";

export function AttachmentList({
  attachments,
  onRemove,
}: {
  attachments: Attachment[];
  onRemove?: (id: string) => void;
}) {
  if (!attachments.length) return null;
  return (
    <VStack gap={2} className="attachment-group">
      <HStack gap={2} wrap="wrap" aria-label="Attachments">
        {attachments.map((attachment) => (
          <HStack key={attachment.id} gap={2} vAlign="center" className="attachment">
            {attachment.previewUrl ? (
              <img
                className="attachment-preview"
                src={attachment.previewUrl}
                alt={`Preview of ${attachment.name}`}
              />
            ) : (
              <HStack className="file-icon" vAlign="center" hAlign="center">
                <FileText size={22} aria-hidden="true" />
              </HStack>
            )}
            <VStack gap={0} className="attachment-details">
              <Text type="label" maxLines={1} hasTruncateTooltip={false}>
                {attachment.name}
              </Text>
              <Text type="supporting" color="secondary">
                {formatFileSize(attachment.size)}
              </Text>
            </VStack>
            {onRemove && (
              <Button
                label={`Remove ${attachment.name}`}
                isIconOnly
                variant="ghost"
                size="sm"
                icon={<X size={16} aria-hidden="true" />}
                onClick={() => onRemove(attachment.id)}
              />
            )}
          </HStack>
        ))}
      </HStack>
      {onRemove && (
        <Text type="supporting" color="secondary">
          Text files are sent with your message.
        </Text>
      )}
    </VStack>
  );
}
