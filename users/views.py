import traceback
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from rest_framework import status,viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from utils.responses import internal_server_error, bad_request, created, not_found, ok
from .models import *
from .serializer import *
import csv
from .blockchain import cast_vote,decrypt_vote
from django.db.models import Count
from collections import defaultdict
from django.shortcuts import get_object_or_404




User = get_user_model()

# Create your views here.
class SignUp(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try: 
            payload = request.data
            serializer = UserSerializer(data=payload)
            if serializer.is_valid(raise_exception=True):
                serializer.save()
                return created(message='User Created successfully')                                   
          
        except ValidationError as err:
            error_message = err.get_full_details()
            print(traceback.format_exc())
            return internal_server_error(message=error_message)
class Login(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            username = request.data.get('username')
            password = request.data.get('password')
            email = request.data.get('email')
            user = authenticate(request=request, email=email, password=password)
            
            if not user:
                return bad_request(message='Invalid credentials')

            if not user.is_active:
                return bad_request(message='User account is disabled')

            refresh = RefreshToken.for_user(user)
            serializer = GetUserSerializer(user)

        
            return ok(data={'user': serializer.data, 'access_token': str(refresh.access_token), 'refresh_token': str(refresh)},message='Login successfully successfully')                                   
          
        except ValidationError as err:
            error_message = err.get_full_details()
            print(traceback.format_exc())
            return internal_server_error(message=error_message)

class ImportCsvView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        csv_file = request.FILES['csv_file']
        # Read and parse the CSV file
        if csv_file:
            file_data = csv_file.read().decode('utf-8').splitlines()
            csv_reader = csv.reader(file_data)
            for row in csv_reader:
                try:
                    name = row[0]
                    father_name = row[1]
                    cnic = row[2]
                    address = row[3]
                    division = row[4]
                    province = row[5]
                    tehsil = row[6]
                    district = row[7]
                    uc_id = row[8]  # Assuming this is an integer in your CSV

                    # Ensure uc_id is an integer
                    uc_id = int(uc_id) if uc_id.isdigit() else None

                    # Use get_or_create with cnic as the unique identifier
                    voter, created = VoterTable.objects.get_or_create(
                        cnic=cnic,  # Ensuring uniqueness on the CNIC field
                        defaults={
                            'name': name,
                            'father_name': father_name,
                            'address': address,
                            'division': division,
                            'province': province,
                            'tehsil': tehsil,
                            'district': district,
                            'uc_id': uc_id
                        }
                    )

                    if created:
                        print(f'New voter created: {name}')
                    else:
                        print(f'Existing voter found: {name}')

                except Exception as e:
                    print(f'Error processing row {row}: {e}')
                    continue

            return Response({'data': 'null', 'message': 'Data Saved Successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'User does not exist'}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        try: 
            all_users = VoterTable.objects.filter().order_by('-date_joined')
            resultdata=[]
            if all_users.exists():
                serializer = VoterUserSerializer(all_users, context={'request': request}, many=True)
                data_send={
                    "count":len(serializer.data),
                   "data":serializer.data,
                }
                return ok(data=data_send)
            else:
                return ok(data=resultdata)
        
        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get voter')


class FindCnicView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        cnic = data.get('cnic')  # Get 'cnic' from the POST request body
        # Read and parse the CSV file
        if cnic:
            # Retrieve voter data based on the provided CNIC
            voter_data = VoterTable.objects.filter(cnic=cnic).first()

            if voter_data:
                # Serialize the voter data
                serializer = VoterUserSerializer(voter_data)

                # Return the serialized data
                return ok(data= serializer.data)
            else:
                return bad_request(message= "CNIC does not exist")
        else:
            return bad_request(message= "CNIC Required")



class ChangePassword(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'message': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        user_instance = User.objects.filter(email=email).first()
        if user_instance:
            user_instance.set_password(password)
            user_instance.is_first_time_login = False
            user_instance.reset_token = None
            user_instance.save()
            return Response({'data': 'null', 'message': 'Password changed successfully'}, status=status.HTTP_200_OK)

        return Response({'message': 'User does not exist'}, status=status.HTTP_400_BAD_REQUEST)

class GetUsers(APIView): 
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try: 
            all_users = User.objects.filter().order_by('-date_joined')
            resultdata=[]
            if all_users.exists():
                paginator = PageNumberPagination()
                paginator.page_size = 10
                result_page = paginator.paginate_queryset(all_users, request)
                serializer = GetUserSerializer(result_page, context={'request': request}, many=True)
                return paginator.get_paginated_response(serializer.data)
            else:
                return ok(data=resultdata)
        
        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get news')


class DeleteUser(APIView):
    def post(self, request):
        try:
            userId = request.data.get('userId')
            user=User.objects.filter(id=userId)
            if not user:
                return not_found(message='Invalid user')
            else:
                user.delete()
                return ok(message='User deleted successfully')                                   
          
        except ValidationError as err:
            error_message = err.get_full_details()
            print(traceback.format_exc())
            return internal_server_error(message=error_message)



# Create your views here.
class ManageProvince(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
                try: 
                    payload_dict = request.data
                    provience_serializer = ProvinceSerializer(data=payload_dict)
                    if provience_serializer.is_valid():
                        provience_serializer.save()
                        message = f"{provience_serializer.validated_data.get('name')} created Successfully "
                    return created(message=message)

                except Exception as err:
                    print(traceback.format_exc())
                    return internal_server_error(message='Failed to create')

    def get(self, request):
        try: 
            all_province = Province.objects.order_by('name')
            resultdata=[]
            if all_province.exists():
                serializer = ProvinceSerializer(all_province, many=True)
                return ok(data=serializer.data)
            else:
                return ok(data=resultdata)
            
        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get room list')

    def delete(self, request):
        try: 
            Pid= request.GET.get('id', None)
            try:
                province = Province.objects.filter(id=Pid).first()
            except Province.DoesNotExist:
                # Handle the case where the object is not found
                messageData="Province not found with id : ".format(Pid)
                return bad_request(message=messageData)
            else:
                # Object was found, do something with it
                province.delete()
                return ok(message='Successfully deleted')
        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete')


class ManageDistrict(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            payload_dict = request.data
            district_serializer = DistrictSerializer(data=payload_dict)
            if district_serializer.is_valid():
                district_serializer.save()
                message = f"{district_serializer.validated_data.get('name')} created successfully"
                return created(message=message)
            return bad_request(message="Invalid data")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to create district')

    def get(self, request, id=None):
        try:
            if id is None:
                return bad_request(message="Province is missing")
            else:
                all_districts = District.objects.filter(province=id).order_by('name')
                resultdata = []
                if all_districts.exists():
                    serializer = DistrictSerializer(all_districts, many=True)
                    return ok(data=serializer.data)
                else:
                    return ok(data=resultdata)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get district list')

    def delete(self, request, id:None):
        try:
            district = District.objects.filter(id=id).first()
            if district:
                district.delete()
                return ok(message='Successfully deleted')
            return bad_request(message=f"District not found with id: {id}")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete district')


class ManageTehsil(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            payload_dict = request.data
            tehsil_serializer = TehsilSerializer(data=payload_dict)
            if tehsil_serializer.is_valid():
                tehsil_serializer.save()
                message = f"{tehsil_serializer.validated_data.get('name')} created successfully"
                return created(message=message)
            return bad_request(message="Invalid data")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to create tehsil')

    def get(self, request, id=None):
        try:
            if id is None:
                return bad_request(message="District is missing")
            else:
                all_tehsils = Tehsil.objects.filter(district=id).order_by('name')
                resultdata = []
                if all_tehsils.exists():
                    serializer = TehsilSerializer(all_tehsils, many=True)
                    return ok(data=serializer.data)
                else:
                    return ok(data=resultdata)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get tehsil list')

    def delete(self, request, id=None):
        try:
            tehsil = Tehsil.objects.filter(id=id).first()
            if tehsil:
                tehsil.delete()
                return ok(message='Successfully deleted')
            return bad_request(message=f"Tehsil not found with id: {id}")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete tehsil')

class ManageDivision(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            payload_dict = request.data
            division_serializer = DivisionSerializer(data=payload_dict)
            if division_serializer.is_valid():
                division_serializer.save()
                message = f"{division_serializer.validated_data.get('name')} created successfully"
                return created(message=message)
            return bad_request(message="Invalid data")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to create division')

    def get(self, request, id=None):
        try:
            
            if id is None:
                return bad_request(message="Tehsil is missing")
            else:
                all_diviosns = Division.objects.order_by('-name')
                resultdata = []
                if all_diviosns.exists():
                    serializer = DivisionSerializer(all_diviosns, many=True)
                    return ok(data=serializer.data)
                else:
                    return ok(data=resultdata)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get division list')

    def delete(self, request, id=None):
        try:
            division = Division.objects.filter(id=id).first()
            if division:
                division.delete()
                return ok(message='Successfully deleted')
            return bad_request(message=f"Division not found with id: {id}")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete Division')



class ManageCouncil(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            payload_dict = request.data
            council_serializer = CouncilSerializer(data=payload_dict)
            if council_serializer.is_valid():
                council_serializer.save()
                message = f"{council_serializer.validated_data.get('name')} created successfully"
                return created(message=message)
            return bad_request(message="Invalid data")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to create tehsil')

    def get(self, request, id=None):
        try:
            if id is None:
                return bad_request(message="Tehsil is missing")
            else:
                all_councils = Council.objects.filter(tehsil=id).order_by('-name')
                resultdata = []
                if all_councils.exists():
                    serializer = CouncilSerializer(all_councils, many=True)
                    return ok(data=serializer.data)
                else:
                    return ok(data=resultdata)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get tehsil list')

    def delete(self, request, id=None):
        try:
            council = Council.objects.filter(id=id).first()
            if council:
                council.delete()
                return ok(message='Successfully deleted')
            return bad_request(message=f"Council not found with id: {id}")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete Council')


class ManagePollingStation(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            payload_dict = request.data
            polling_station_serializer = PollingStationSerializer(data=payload_dict)
            if polling_station_serializer.is_valid():
                polling_station_serializer.save()
                message = f"{polling_station_serializer.validated_data.get('name')} created successfully"
                return created(message=message)
            return bad_request(message="Invalid data")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to create polling station')

    def get(self, request, id=None):
        try:
            if id is None:
                return bad_request(message="Tehsil is missing")
            else:
                all_polling_stations = PollingStation.objects.order_by('name')
                resultdata = []
                if all_polling_stations.exists():
                    serializer = PollingStationSerializer(all_polling_stations, many=True)
                    return ok(data=serializer.data)
                else:
                    return ok(data=resultdata)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get polling station list')

    def delete(self, request, id=None):
        try:
            polling_station = PollingStation.objects.filter(id=id).first()
            if polling_station:
                polling_station.delete()
                return ok(message='Successfully deleted')
            return bad_request(message=f"Polling station not found with id: {id}")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete polling station')


class ManagePollingBooth(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            payload_dict = request.data
            polling_booth_serializer = PollingBoothSerializer(data=payload_dict)
            if polling_booth_serializer.is_valid():
                polling_booth_serializer.save()
                message = f"{polling_booth_serializer.validated_data.get('name')} created successfully"
                return created(message=message)
            return bad_request(message="Invalid data")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to create polling booth')

    def get(self, request, id=None):
        try:
            if id is None:
                return bad_request(message="Tehsil is missing")
            else:
                all_polling_booths = PollingBooth.objects.order_by('name')
                resultdata = []
                if all_polling_booths.exists():
                    serializer = PollingBoothSerializer(all_polling_booths, many=True)
                    return ok(data=serializer.data)
                else:
                    return ok(data=resultdata)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get polling booth list')

    def delete(self, request, id=None):
        try:
            polling_booth = PollingBooth.objects.filter(id=id).first()
            if polling_booth:
                polling_booth.delete()
                return ok(message='Successfully deleted')
            return bad_request(message=f"Polling booth not found with id: {id}")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete polling booth')



class ManageCandidate(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            payload_dict = request.data
            candidate_serializer = CandidateSerializer(data=payload_dict)
            if candidate_serializer.is_valid():
                candidate_serializer.save()
                message = f"{candidate_serializer.validated_data.get('name')} created successfully"
                return created(message=message)
            return bad_request(message=candidate_serializer.errors)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to create polling station')

    def get(self, request, id=None):
        try:
            if id is None:
                return bad_request(message='Polling Station ID is missing')
            else:
                all_candiates = Candidate.objects.filter(polling_station=id).order_by('-modified_datetime')
                resultdata = []
                if all_candiates.exists():
                    serializer = CandidateSerializer(all_candiates, many=True)
                    return ok(data=serializer.data)
                else:
                    return ok(data=resultdata)

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to get candidate list')

    def delete(self, request, id=None):
        try:
            candidate = Candidate.objects.filter(id=id).first()
            if candidate:
                candidate.delete()
                return ok(message='Successfully deleted')
            return bad_request(message=f"Candidate not found with id: {id}")

        except Exception as err:
            print(traceback.format_exc())
            return internal_server_error(message='Failed to delete Candidate')


class VoterViewSet(viewsets.ViewSet):

    def list_voters(self, request):
        # Filter by province, district, tehsil, etc.
        filters = {
            'province': request.query_params.get('province'),
            'district': request.query_params.get('district'),
            'tehsil': request.query_params.get('tehsil'),
            'council': request.query_params.get('council'),
            'polling_station': request.query_params.get('polling_station'),
        }
        voters = VoterTable.objects.filter(**{k: v for k, v in filters.items() if v is not None})
        serializer = VoterUserSerializer(voters, many=True)
        return ok(data=serializer.data)

    def get_candidate_list(self, request):
        # Filter candidates by the same parameters
        filters = {
            'province': request.query_params.get('province'),
            'district': request.query_params.get('district'),
            'tehsil': request.query_params.get('tehsil'),
            'council': request.query_params.get('council'),
            'polling_station': request.query_params.get('polling_station'),
        }
        candidates = Candidate.objects.filter(**{k: v for k, v in filters.items() if v is not None})
        serializer = CandidateSerializer(candidates, many=True)
        return ok(data=serializer.data)

    def voter_statistics(self, request):
        # Compare registered and casted voters in polling stations
        polling_station_id = request.query_params.get('polling_station_id')
        polling_station = PollingStation.objects.get(id=polling_station_id)
        registered_voters = VoterTable.objects.filter(polling_station=polling_station).count()
        casted_voters = Vote.objects.filter(candidate__polling_station=polling_station).values('voter').distinct().count()

        data = {
            'registered_voters': registered_voters,
            'casted_voters': casted_voters,
        }
        return ok(data=data)

    def candidate_details(self, request, pk=None):
        # Get candidate profile detail and votes
        candidate = Candidate.objects.get(pk=pk)
        votes = Vote.objects.filter(candidate=candidate).count()
        total_votes = Vote.objects.count()
        percentage = (votes / total_votes) * 100 if total_votes > 0 else 0

        data = {
            'candidate': CandidateSerializer(candidate).data,
            'total_votes': votes,
            'percentage': percentage,
        }
        return ok(data=data)
    def dashboard_details(self, request, pk=None):
        # Get candidate profile detail and votes
        try:
            # Get all polling stations under the given council
            polling_stations_count = PollingStation.objects.filter(council_id=pk).count()
            candidates_count = Candidate.objects.filter(council_id=pk).count()
            total_votes_count = VoterTable.objects.filter(council_id=pk).count()
            casted_votes_count = Vote.objects.filter(council_id=pk).count()
            remaining_votes_count = total_votes_count - casted_votes_count

            # Prepare the response
            data = {
                "polling_stations_count": polling_stations_count,
                "candidates_count": candidates_count,
                "total_votes_count": total_votes_count,
                "casted_votes_count": casted_votes_count,
                "remaining_votes_count": remaining_votes_count
            }
            return ok(data=data)
        except Council.DoesNotExist:
            return internal_server_error(message= "Council not found")
    def get_polling_station_vote_stats(self, request, pk=None):
        # Get total votes registered in the polling station
        total_votes_registered = VoterTable.objects.filter(polling_station_id=pk).count()

        # Get total votes cast in the polling station
        total_votes_cast = Vote.objects.filter(voter__polling_station_id=pk).count()

        # Get male votes
        male_votes_count = Vote.objects.filter(
            voter__polling_station_id=pk,
            gender='Male'  # Assuming gender is stored as 'Male' or 'Female'
        ).count()

        # Get female votes
        female_votes_count = Vote.objects.filter(
            voter__polling_station_id=pk,
            gender='Female'  # Assuming gender is stored as 'Male' or 'Female'
        ).count()

        return ok(data={
            'total_votes_registered': total_votes_registered,
            'total_votes_cast': total_votes_cast,
            'male_votes': male_votes_count,
            'female_votes': female_votes_count,
        }) 
    def get_male_votes_in_booths(self, request, pk=None):
        # Get booths in the polling station
        booths = PollingBooth.objects.filter(polling_station_id=pk, gender='Male')
        
        # Initialize list to store booth votes statistics
        booth_votes_stats = []
        total_votes_sum = 0  # Initialize a variable to sum total votes

        for booth in booths:
            # Get total votes in the booth (both male and female)
            total_votes_count = Vote.objects.filter(
                voter__polling_booth_id=booth.id
            ).count()
            total_votes_sum += total_votes_count
            booth_votes_stats.append({
                'booth_id': booth.id,
                'name': booth.name,
                'total_votes': total_votes_count,
            })

        return ok(data={
            'booth_votes': booth_votes_stats,
            'total_votes_sum': total_votes_sum,  # Total sum of votes across all booths
            })
    def get_female_votes_in_booths(self, request, pk=None):
        # Get booths in the polling station
        booths = PollingBooth.objects.filter(polling_station_id=pk, gender='Female')
        
        # Initialize list to store booth votes statistics
        booth_votes_stats = []
        total_votes_sum = 0  # Initialize a variable to sum total votes

        for booth in booths:
            # Get total votes in the booth (both male and female)
            total_votes_count = Vote.objects.filter(
                voter__polling_booth_id=booth.id
            ).count()
            total_votes_sum += total_votes_count
            booth_votes_stats.append({
                'booth_id': booth.id,
                'name': booth.name,
                'total_votes': total_votes_count,
            })

        return ok(data={
            'booth_votes': booth_votes_stats,
            'total_votes_sum': total_votes_sum,  # Total sum of votes across all booths
            })


class CastVote(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            voter_id = request.data.get('voter')
            candidate_id = request.data.get('candidate')
            council_id =  request.data.get('council')
            polling_station_id =  request.data.get('polling_station')
            polling_booth_id =  request.data.get('polling_booth')
            gender =  request.data.get('gender')
            voter = VoterTable.objects.get(id=voter_id)
            candidate = Candidate.objects.get(id=candidate_id)
            council = Council.objects.get(id=council_id)
            polling_station = PollingStation.objects.get(id=polling_station_id)
            polling_booth = PollingBooth.objects.get(id=polling_booth_id)
            if Vote.objects.filter(voter=voter, candidate=candidate).exists():
                  return bad_request(message="Vote already casted")
            else:
                txn_id = cast_vote(voter, candidate,council,polling_station,polling_booth,gender)
                return created(message= "Vote cast successfully", data={"transaction_id": txn_id})
        except ValidationError as err:
            error_message = err.get_full_details()
            print(traceback.format_exc())
            return internal_server_error(message=error_message)
    def get(self, request, id=None):
        try:
            # Retrieve votes for the specific candidate
            # Get all CatsedVotes
            catsed_votes = CatsedVote.objects.all()
            
            # Group votes by candidate
            vote_data = []

            # Decrypt the transaction_id from CatsedVote and fetch related votes
            for catsed_vote in catsed_votes:
                # Decrypt the transaction ID to get the vote ID
                decrypted_vote_id = decrypt_vote(catsed_vote.transaction_id)
                # Retrieve the Vote object using the decrypted vote ID
                try:
                    vote = Vote.objects.get(id=decrypted_vote_id)            
                    # Prepare vote data (you can expand this as needed)
                    serilizeData = VoteGetterSerializer(vote, partial=True)
                    vote_data.append(serilizeData.data)
                except Vote.DoesNotExist:
                    continue  # If the vote doesn't exist for this ID, skip it
            return ok(data={
                "votes": vote_data,
                "vote_count": len(vote_data),
            })

        except Candidate.DoesNotExist:
            return not_found(message= "Candidate not found.")
        except Exception as e:
            return internal_server_error(message=str(e))

class CouncilStatisticsView(APIView):
    def get(self, request, council_id):
        try:
            council = Council.objects.get(id=council_id)

            # Total votes cast against this council
            total_casted_votes = Vote.objects.filter(candidate__council=council).count()

            # Total unique voters (distinct voters who have cast a vote in this council)
            total_voters = Vote.objects.filter(candidate__council=council).values('voter').distinct().count()

            # Total polling stations in this council
            total_polling_stations = PollingStation.objects.filter(council=council).count()

            # Total candidates in this council
            total_candidates = Candidate.objects.filter(council=council).count()

            # Prepare the response
            data = {
                "council_name": council.name,
                "total_casted_votes": total_casted_votes,
                "total_voters": total_voters,
                "total_polling_stations": total_polling_stations,
                "total_candidates": total_candidates
            }
            return ok(data=data)
        
        except Council.DoesNotExist:
            return internal_server_error(message= "Council not found")

class PollingStationCandidatesView(APIView):
    def get(self, request, id:None):
        try:
            # Get the polling station
            polling_station = PollingStation.objects.get(id=id)

            # Annotate each candidate with the count of votes they received at this polling station,
            # and order by the vote count in descending order
            candidates = Candidate.objects.filter(polling_station=polling_station)\
                .annotate(vote_count=Count('vote'))\
                .order_by('-vote_count')
            total_votes_cast = Vote.objects.filter(voter__polling_station_id=id).count()
            total_votes_registered = VoterTable.objects.filter(polling_station_id=id).count()

            # Prepare response data
            candidates_data = [
                {
                    "candidate_name": candidate.name,
                    "type": candidate.type,
                    "vote_count": candidate.vote_count
                } for candidate in candidates
            ]

            data = {
                "polling_station": polling_station.name,
                "total_votes_cast":total_votes_cast,
                "total_votes_registered":total_votes_registered,
                "candidates": candidates_data,
            }
            return ok(data=data)

        except PollingStation.DoesNotExist:
            return internal_server_error(message= "Polling station not found")


class RegisterFingerprint(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            cnic = request.data.get('cnic')
            fingerprint = request.data.get('fingerprint')
            if not cnic or not fingerprint:
                return bad_request(message= "Both cnic and fingerprint are required." )

            # Fetch voter from the database
            voter = get_object_or_404(VoterTable, cnic=cnic)

            # Update the fingerprint
            voter.fingerprint = fingerprint
            voter.save()
            return ok(message="Fingerprint Register successfully")
           
        except ValidationError as err:
            error_message = err.get_full_details()
            print(traceback.format_exc())
            return internal_server_error(message=error_message)


class CastVoteView(APIView):
    authentication_classes = []
    permission_classes = []
    def post(self, request):
        try:
            voter_id = request.data.get('voter')
            fingerprint = request.data.get('fingerprint')
            candidate_id = request.data.get('candidate')
            council_id =  request.data.get('council')
            polling_station_id =  request.data.get('polling_station')
            polling_booth_id =  request.data.get('polling_booth')
            gender =  request.data.get('gender')
            if not fingerprint:
                return bad_request(message="Fingerprint is required")

            # Fetch voter by fingerprint
            try:
                voter = VoterTable.objects.get(fingerprint=fingerprint)
            except VoterTable.DoesNotExist:
                return bad_request(message="Voter with the provided fingerprint does not exist")
            voter = VoterTable.objects.get(id=voter_id)
            candidate = Candidate.objects.get(id=candidate_id)
            council = Council.objects.get(id=council_id)
            polling_station = PollingStation.objects.get(id=polling_station_id)
            polling_booth = PollingBooth.objects.get(id=polling_booth_id)
            if Vote.objects.filter(voter=voter, candidate=candidate).exists():
                  return bad_request(message="Vote already casted")
            else:
                txn_id = cast_vote(voter, candidate,council,polling_station,polling_booth,gender)
                return created(message= "Vote cast successfully", data={"transaction_id": txn_id})
        except ValidationError as err:
            error_message = err.get_full_details()
            print(traceback.format_exc())
            return internal_server_error(message=error_message)