import axios from "axios";

const generateImageURL = async (image) => {
  const file = new FormData();
  file.append("file", image);
  const uploadPreset = import.meta.env.VITE_CLOUDINARY_PRESET;
  const cloudName = import.meta.env.VITE_CLOUDINARY_CLOUD_NAME;

  if (!uploadPreset || !cloudName) {
    throw new Error("Cloudinary is not configured. Set VITE_CLOUDINARY_PRESET and VITE_CLOUDINARY_CLOUD_NAME.");
  }

  file.append("upload_preset", uploadPreset);

  const { data } = await axios.post(
    `https://api.cloudinary.com/v1_1/${cloudName}/image/upload`,
    file
  );
  return data;
};

export default generateImageURL;
