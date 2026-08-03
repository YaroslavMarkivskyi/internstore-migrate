// Third-party imports
import fs from 'fs';
import path, { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

import {
  DeleteObjectsCommand,
  ListObjectsCommand,
  PutObjectCommand,
  S3Client,
} from '@aws-sdk/client-s3';
import * as dotenv from 'dotenv';
import mime from 'mime-types';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load environment variables
dotenv.config({ path: resolve(__dirname, '../.env') });

// Verify credentials are loaded
console.log('Deploying to bucket:', process.env.AWS_S3_BUCKET);
console.log('Using region:', process.env.AWS_REGION);
console.log(
  'Access key present:',
  process.env.AWS_ACCESS_KEY_ID ? 'Yes' : 'No'
);
console.log(
  'Secret key present:',
  process.env.AWS_SECRET_ACCESS_KEY ? 'Yes' : 'No'
);

// Configuration
const BUCKET_NAME = process.env.AWS_S3_BUCKET;
const REGION = process.env.AWS_REGION || 'us-east-1';
const BUILD_DIR = path.resolve(__dirname, '../dist');

// Initialize S3 client
const s3Client = new S3Client({
  region: REGION,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
  },
});

// Function to recursively read all files in a directory
function readFilesRecursively(dir, fileList = []) {
  const files = fs.readdirSync(dir);

  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      readFilesRecursively(filePath, fileList);
    } else {
      fileList.push(filePath);
    }
  });

  return fileList;
}

// Function to clear existing files in the bucket (optional)
// eslint-disable-next-line no-unused-vars
async function clearBucket() {
  try {
    const listCommand = new ListObjectsCommand({ Bucket: BUCKET_NAME });
    const { Contents } = await s3Client.send(listCommand);

    if (Contents && Contents.length > 0) {
      const deleteParams = {
        Bucket: BUCKET_NAME,
        Delete: {
          Objects: Contents.map(item => ({ Key: item.Key })),
        },
      };

      await s3Client.send(new DeleteObjectsCommand(deleteParams));
      console.log('Cleared existing files from bucket');
    }
  } catch (err) {
    console.error('Error clearing bucket:', err);
  }
}

// Function to upload files to S3
async function uploadToS3() {
  try {
    // Optionally clear the bucket first
    // await clearBucket();

    // Get all files from build directory
    const files = readFilesRecursively(BUILD_DIR);

    // Upload each file
    const uploadPromises = files.map(async filePath => {
      const relativeFilePath = path.relative(BUILD_DIR, filePath);
      const key = relativeFilePath.replace(/\\/g, '/'); // Ensure forward slashes for S3 keys
      const fileContent = fs.readFileSync(filePath);
      const contentType = mime.lookup(filePath) || 'application/octet-stream';

      const params = {
        Bucket: BUCKET_NAME,
        Key: key,
        Body: fileContent,
        ContentType: contentType,
        CacheControl: getCacheControl(key),
      };

      await s3Client.send(new PutObjectCommand(params));
      console.log(`Uploaded: ${key}`);
    });

    await Promise.all(uploadPromises);
    console.log('Deployment complete!');
  } catch (err) {
    console.error('Deployment failed:', err);
    process.exit(1);
  }
}

// Set appropriate cache control headers based on file type
function getCacheControl(key) {
  if (key.match(/\.(html|htm)$/i)) {
    // Don't cache HTML files
    return 'no-cache, no-store, must-revalidate';
  } else if (key.match(/\.(js|css|png|jpg|jpeg|gif|svg|webp)$/i)) {
    // Cache assets with hash in filename for 1 year
    if (key.match(/[0-9a-f]{8,}/i)) {
      return 'public, max-age=31536000, immutable';
    }
  }
  // Default cache policy
  return 'public, max-age=86400'; // 1 day
}

// Execute the deployment
uploadToS3().catch(err => {
  console.error('Unhandled error:', err);
  process.exit(1);
});
