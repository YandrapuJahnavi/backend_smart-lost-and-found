import math
import os
import re
import json
import logging
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from PIL import Image
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Check if CLIP / PyTorch is available in the environment
CLIP_AVAILABLE = False
clip_model = None
clip_processor = None

try:
    import torch
    from transformers import CLIPProcessor, CLIPModel
    logger.info("PyTorch and Transformers detected, verifying CLIP model availability...")
    # Only set True if model weights can actually be instantiated
    CLIP_AVAILABLE = False  # Keep false unless explicit pretrained weights are loaded
except Exception:
    CLIP_AVAILABLE = False


def validate_image_file(image_path: str) -> bool:
    """Validate that the file exists, is openable by Pillow and has valid dimensions."""
    if not image_path or not os.path.exists(image_path):
        return False
    try:
        with Image.open(image_path) as img:
            img.verify()
        return True
    except Exception as e:
        logger.warning(f"Image validation failed for {image_path}: {e}")
        return False


def extract_genuine_512_descriptor(image_path: str) -> List[float]:
    """
    Genuine 512-dimensional computer vision feature descriptor using Pillow & NumPy.
    Extracts exactly 512 real image-derived measurements with ZERO artificial padding:

    1. 8x8 Spatial Grid RGB Distribution (384 dimensions):
       - 64 spatial blocks across the 224x224 image
       - Per-block RGB Means: 64 * 3 = 192 dimensions
       - Per-block RGB Standard Deviations: 64 * 3 = 192 dimensions
       Total: 384 dimensions

    2. Global HSV Color Palette Histogram (64 dimensions):
       - 32-bin Hue distribution (capturing chromatic identity)
       - 16-bin Saturation distribution (capturing vividness vs neutral tone)
       - 16-bin Value distribution (capturing dark/black vs light/white tone)
       Total: 64 dimensions

    3. Directional Edge Orientation Histogram (64 dimensions):
       - Sobel gradient angles [-pi, pi] quantized into 64 directional bins
       - Bins weighted by gradient magnitude (capturing structural shape and geometry)
       Total: 64 dimensions

    Grand Total: 384 + 64 + 64 = 512 dimensions.
    """
    try:
        with Image.open(image_path) as img:
            img_rgb = img.convert('RGB')
            img_rgb = img_rgb.resize((224, 224), Image.Resampling.BILINEAR)
            arr = np.array(img_rgb, dtype=np.float32) / 255.0  # (224, 224, 3)

            # ---------------------------------------------------------
            # Part 1: 8x8 Spatial Grid (384 dimensions)
            # ---------------------------------------------------------
            spatial = []
            bh = 224 // 8  # 28 pixels
            bw = 224 // 8  # 28 pixels
            for i in range(8):
                for j in range(8):
                    block = arr[i * bh:(i + 1) * bh, j * bw:(j + 1) * bw, :]
                    means = block.mean(axis=(0, 1))  # 3 values
                    stds = block.std(axis=(0, 1))    # 3 values
                    spatial.extend(means.tolist())
                    spatial.extend(stds.tolist())
            spatial_vec = np.array(spatial, dtype=np.float32)  # 384 dims

            # ---------------------------------------------------------
            # Part 2: Global HSV Histogram (64 dimensions)
            # ---------------------------------------------------------
            img_hsv = img_rgb.convert('HSV')
            hsv_arr = np.array(img_hsv, dtype=np.float32) / 255.0

            h_hist, _ = np.histogram(hsv_arr[:, :, 0], bins=32, range=(0.0, 1.0))
            s_hist, _ = np.histogram(hsv_arr[:, :, 1], bins=16, range=(0.0, 1.0))
            v_hist, _ = np.histogram(hsv_arr[:, :, 2], bins=16, range=(0.0, 1.0))

            h_norm = h_hist.astype(np.float32) / (h_hist.sum() + 1e-7)
            s_norm = s_hist.astype(np.float32) / (s_hist.sum() + 1e-7)
            v_norm = v_hist.astype(np.float32) / (v_hist.sum() + 1e-7)
            hsv_vec = np.concatenate([h_norm, s_norm, v_norm])  # 64 dims

            # ---------------------------------------------------------
            # Part 3: Directional Edge Orientation Histogram (64 dimensions)
            # ---------------------------------------------------------
            gray = 0.2989 * arr[:, :, 0] + 0.5870 * arr[:, :, 1] + 0.1140 * arr[:, :, 2]
            dx = np.zeros_like(gray)
            dy = np.zeros_like(gray)
            dx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
            dy[1:-1, :] = gray[2:, :] - gray[:-2, :]

            mag = np.sqrt(dx**2 + dy**2)
            angles = np.arctan2(dy, dx)  # [-pi, pi]
            edge_hist, _ = np.histogram(angles, bins=64, range=(-np.pi, np.pi), weights=mag)
            edge_vec = edge_hist.astype(np.float32) / (edge_hist.sum() + 1e-7)  # 64 dims

            # ---------------------------------------------------------
            # Normalization & Balanced Weighted Fusion
            # ---------------------------------------------------------
            sp_norm = np.linalg.norm(spatial_vec)
            if sp_norm > 0:
                spatial_vec = spatial_vec / sp_norm

            hsv_norm = np.linalg.norm(hsv_vec)
            if hsv_norm > 0:
                hsv_vec = hsv_vec / hsv_norm

            edge_norm = np.linalg.norm(edge_vec)
            if edge_norm > 0:
                edge_vec = edge_vec / edge_norm

            # Weight distribution: 50% spatial layout, 30% color palette, 20% edge/texture structure
            combined = np.concatenate([
                0.50 * spatial_vec,
                0.30 * hsv_vec,
                0.20 * edge_vec
            ])

            # Final L2 normalization
            total_norm = np.linalg.norm(combined)
            if total_norm > 0:
                final_vec = combined / total_norm
            else:
                final_vec = combined

            return final_vec.tolist()
    except Exception as e:
        logger.error(f"Error computing genuine 512-D descriptor for {image_path}: {e}")
        return [0.0] * 512


def generate_item_embedding(image_path: str) -> Tuple[List[float], str]:
    """Generates embedding using CLIP if available, otherwise genuine 512-D computer vision descriptor."""
    if not validate_image_file(image_path):
        return [], 'none'

    # If CLIP is loaded/active, use CLIP embeddings
    global CLIP_AVAILABLE, clip_model, clip_processor
    if CLIP_AVAILABLE and clip_model is not None and clip_processor is not None:
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = clip_processor(images=image, return_tensors="pt")
            with torch.no_grad():
                image_features = clip_model.get_image_features(**inputs)
                image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
                embedding = image_features.squeeze().cpu().numpy().tolist()
                return embedding, 'clip-vit-base-patch32'
        except Exception as e:
            logger.warning(f"CLIP embedding failed, falling back to genuine 512-D descriptor: {e}")

    # Fallback: Genuine 512-D Pillow + NumPy Descriptor (No artificial padding)
    vector = extract_genuine_512_descriptor(image_path)
    return vector, 'pillow_spatial_hsv_gradient_512'


def calculate_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculates cosine similarity between two float vectors (0.0 to 100.0%)."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    u = np.array(vec1, dtype=np.float32)
    v = np.array(vec2, dtype=np.float32)
    norm_u = np.linalg.norm(u)
    norm_v = np.linalg.norm(v)
    if norm_u == 0 or norm_v == 0:
        return 0.0
    dot = float(np.dot(u, v) / (norm_u * norm_v))
    # Never convert raw negative or low cosine values to artificially high percentages
    sim = max(0.0, min(1.0, dot))
    return round(sim * 100.0, 2)


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points on the Earth in kilometers."""
    R = 6371.0  # Earth's radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def calculate_location_score(item1, item2) -> Tuple[float, Optional[float]]:
    """
    Calculates geographical proximity score (0-100) and distance in km.
    When coordinates are missing, returns (score, None).
    Never invents distances or claims region match without evidence.
    """
    has_coords1 = item1.latitude is not None and item1.longitude is not None
    has_coords2 = item2.latitude is not None and item2.longitude is not None

    if has_coords1 and has_coords2:
        try:
            dist = calculate_haversine_distance(
                float(item1.latitude), float(item1.longitude),
                float(item2.latitude), float(item2.longitude)
            )
            # Distance scoring curve based on exact km distance
            if dist <= 1.0:
                score = 100.0
            elif dist <= 5.0:
                score = 90.0 - (dist - 1.0) * 2.5
            elif dist <= 20.0:
                score = 80.0 - (dist - 5.0) * 1.5
            elif dist <= 50.0:
                score = 55.0 - (dist - 20.0) * 0.8
            elif dist <= 100.0:
                score = 30.0 - (dist - 50.0) * 0.4
            else:
                score = max(0.0, 10.0 - (dist - 100.0) * 0.05)
            return round(score, 2), dist
        except Exception:
            pass

    # If coordinates are missing on either item: DO NOT invent distances
    loc1 = (item1.location or '').lower()
    loc2 = (item2.location or '').lower()

    # Generic stop words to prevent false area matches
    geo_stopwords = {
        'near', 'station', 'park', 'street', 'road', 'avenue', 'lane', 'gate',
        'walking', 'path', 'bench', 'floor', 'desk', 'room', 'building', 'center',
        'the', 'and', 'with', 'from', 'food', 'court', 'entrance', 'exit', 'hall'
    }
    words1 = set([w for w in re.findall(r'\b\w{4,}\b', loc1) if w not in geo_stopwords])
    words2 = set([w for w in re.findall(r'\b\w{4,}\b', loc2) if w not in geo_stopwords])

    # If genuine specific city/area words match
    if words1 and words2 and (words1 & words2):
        return 50.0, None

    # No coordinates and no verifiable area match -> 0.0% location contribution
    return 0.0, None


def calculate_color_score(color1: str, color2: str) -> float:
    """Compares color descriptions with taxonomy awareness."""
    c1 = (color1 or '').lower().strip()
    c2 = (color2 or '').lower().strip()
    if not c1 or not c2:
        return 30.0
    if c1 == c2:
        return 100.0
    words1 = set(re.findall(r'\b\w+\b', c1))
    words2 = set(re.findall(r'\b\w+\b', c2))
    if words1 & words2:
        return 85.0

    # Common synonyms/families
    families = [
        {'black', 'dark', 'charcoal', 'midnight', 'jet'},
        {'white', 'ivory', 'silver', 'cream'},
        {'blue', 'navy', 'sky', 'teal', 'cyan', 'indigo'},
        {'red', 'crimson', 'burgundy', 'maroon', 'rose', 'pink'},
        {'brown', 'tan', 'beige', 'khaki', 'chocolate'},
        {'gray', 'grey', 'silver', 'metallic'},
        {'green', 'olive', 'emerald', 'mint'},
        {'yellow', 'gold', 'mustard', 'amber'},
    ]
    for fam in families:
        if (words1 & fam) and (words2 & fam):
            return 70.0

    return 10.0


def calculate_text_score(item1, item2) -> float:
    """Calculates lexical and semantic overlap between titles and descriptions."""
    text1 = f"{item1.title} {item1.description}".lower()
    text2 = f"{item2.title} {item2.description}".lower()

    stopwords = {'a', 'an', 'the', 'in', 'on', 'at', 'with', 'and', 'or', 'for', 'to', 'of', 'my', 'is', 'was', 'it'}
    tokens1 = set([w for w in re.findall(r'\b\w{3,}\b', text1) if w not in stopwords])
    tokens2 = set([w for w in re.findall(r'\b\w{3,}\b', text2) if w not in stopwords])

    if not tokens1 or not tokens2:
        return 15.0

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard = len(intersection) / len(union)

    # Title match bonus
    title_words1 = set(re.findall(r'\b\w{3,}\b', item1.title.lower())) - stopwords
    title_words2 = set(re.findall(r'\b\w{3,}\b', item2.title.lower())) - stopwords
    title_overlap = len(title_words1 & title_words2)

    score = (jaccard * 70.0) + (min(title_overlap, 3) * 10.0)
    return round(min(100.0, score), 2)


def compute_multi_factor_match(lost_item, found_item) -> Dict[str, Any]:
    """
    Combines visual cosine similarity with category, colour, description and proximity.
    Weights:
      Visual similarity:    40%
      Category match:       25%
      Colour similarity:    15%
      Textual overlap:      10%
      Location proximity:   10%
    """
    # 1. Visual Cosine Similarity
    visual_score = 0.0
    if lost_item.image_embedding and found_item.image_embedding:
        visual_score = calculate_cosine_similarity(lost_item.image_embedding, found_item.image_embedding)
    elif lost_item.image and found_item.image:
        emb_lost, _ = generate_item_embedding(lost_item.image.path) if lost_item.image else ([], '')
        emb_found, _ = generate_item_embedding(found_item.image.path) if found_item.image else ([], '')
        if emb_lost and emb_found:
            visual_score = calculate_cosine_similarity(emb_lost, emb_found)

    # 2. Category Score
    if lost_item.category == found_item.category:
        category_score = 100.0
    else:
        category_score = 0.0

    # 3. Colour Score
    color_score = calculate_color_score(lost_item.colour, found_item.colour)

    # 4. Text / Keyword Overlap
    text_score = calculate_text_score(lost_item, found_item)

    # 5. Location Proximity
    loc_score, dist_km = calculate_location_score(lost_item, found_item)

    # Combined composite score
    total_score = (
        (visual_score * 0.40) +
        (category_score * 0.25) +
        (color_score * 0.15) +
        (text_score * 0.10) +
        (loc_score * 0.10)
    )
    total_score = round(min(100.0, max(0.0, total_score)), 2)

    breakdown = {
        'visual_similarity_percent': visual_score,
        'category_score_percent': category_score,
        'color_score_percent': color_score,
        'text_score_percent': text_score,
        'location_score_percent': loc_score,
        'approx_distance_km': dist_km,
        'disclaimer': 'Similarity score is an automated AI assistance indicator and never constitutes legal proof of ownership.'
    }

    return {
        'total_score': total_score,
        'visual_score': visual_score,
        'category_score': category_score,
        'color_score': color_score,
        'text_score': text_score,
        'location_score': loc_score,
        'distance_km': dist_km,
        'breakdown': breakdown
    }


def find_and_save_matches_for_item(item, opposite_items_qs) -> List[Any]:
    """
    Takes an item (either LostItem or FoundItem) and compares it against active opposite items.
    Saves or updates MatchRecord in MySQL and creates notifications for high-confidence matches.
    """
    from items.models import LostItem, FoundItem
    from matching.models import MatchRecord
    from notifications.models import Notification

    is_lost = isinstance(item, LostItem)
    created_matches = []

    # Ensure current item has embeddings if image exists
    if item.image and (not item.image_embedding or not item.feature_extracted or item.embedding_model != 'pillow_spatial_hsv_gradient_512'):
        emb, model_name = generate_item_embedding(item.image.path)
        if emb:
            item.image_embedding = emb
            item.embedding_model = model_name
            item.feature_extracted = True
            item.save(update_fields=['image_embedding', 'embedding_model', 'feature_extracted'])

    for opp in opposite_items_qs:
        # Skip if opposite item belongs to the same user
        if opp.user_id == item.user_id:
            continue

        # Ensure opposite item has embedding if image exists
        if opp.image and (not opp.image_embedding or not opp.feature_extracted or opp.embedding_model != 'pillow_spatial_hsv_gradient_512'):
            emb_opp, mname_opp = generate_item_embedding(opp.image.path)
            if emb_opp:
                opp.image_embedding = emb_opp
                opp.embedding_model = mname_opp
                opp.feature_extracted = True
                opp.save(update_fields=['image_embedding', 'embedding_model', 'feature_extracted'])

        lost_obj = item if is_lost else opp
        found_obj = opp if is_lost else item

        match_data = compute_multi_factor_match(lost_obj, found_obj)
        score = match_data['total_score']

        # Only save if score meets minimum threshold (e.g. >= 25.0)
        if score >= 25.0:
            match_record, created = MatchRecord.objects.update_or_create(
                lost_item=lost_obj,
                found_item=found_obj,
                defaults={
                    'similarity_score': score,
                    'visual_score': match_data['visual_score'],
                    'category_score': match_data['category_score'],
                    'color_score': match_data['color_score'],
                    'text_score': match_data['text_score'],
                    'location_score': match_data['location_score'],
                    'distance_km': match_data['distance_km'],
                    'breakdown': match_data['breakdown'],
                }
            )
            created_matches.append(match_record)

            # High confidence alert (>= 50%) generates notifications to both users
            if score >= 50.0:
                if lost_obj.status == 'open':
                    lost_obj.status = 'matched'
                    lost_obj.save(update_fields=['status'])
                if found_obj.status == 'open':
                    found_obj.status = 'matched'
                    found_obj.save(update_fields=['status'])

                # Notify lost item owner
                Notification.objects.get_or_create(
                    user=lost_obj.user,
                    notification_type='match',
                    title=f"Potential Match ({score}%): {found_obj.title}",
                    defaults={
                        'message': f"A found item '{found_obj.title}' in category '{found_obj.get_category_display()}' was matched with your lost '{lost_obj.title}' with {score}% similarity.",
                        'link': f"/matches"
                    }
                )

                # Notify found item reporter
                Notification.objects.get_or_create(
                    user=found_obj.user,
                    notification_type='match',
                    title=f"Potential Match ({score}%): {lost_obj.title}",
                    defaults={
                        'message': f"Your found item '{found_obj.title}' closely matches a lost report for '{lost_obj.title}' ({score}% similarity).",
                        'link': f"/matches"
                    }
                )

                # Send email notification if user email is present
                try:
                    if lost_obj.user.email:
                        send_mail(
                            subject=f"[Smart Lost & Found] Potential Match Found for '{lost_obj.title}'",
                            message=f"Hello {lost_obj.user.username},\n\nOur AI matching engine discovered a {score}% potential match for your lost item '{lost_obj.title}'.\n\nFound Item: {found_obj.title}\nLocation: {found_obj.location}\nDate: {found_obj.date_found}\n\nPlease visit the platform to view the match details and submit a claim if it is yours.\n\nSmart Lost & Found Team",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[lost_obj.user.email],
                            fail_silently=True
                        )
                except Exception as e:
                    logger.warning(f"Failed to send email to {lost_obj.user.email}: {e}")

    return created_matches
